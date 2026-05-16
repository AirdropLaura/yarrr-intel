"""Etherscan V2 provider — multichain via `chainid` parameter.

One API key (free tier 5 calls/sec) covers ~22 mainnets + testnets. We respect
the rate limit with a real token-bucket limiter (not just a concurrency
semaphore — that doesn't bound RPS when responses are fast). Each sub-call
gets retried with exponential backoff so transient timeouts and rate-limit
hits don't silently zero out a chain.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time

import httpx

from . import ChainProvider, register

log = logging.getLogger("yarrr-tech.providers.etherscan")

ETHERSCAN_BASE = "https://api.etherscan.io/v2/api"


class _TokenBucket:
    """Simple async token bucket — caps real RPS, not just concurrency.

    Etherscan free tier is 5 RPS shared across all chains. We pace at 4 RPS to
    leave headroom for retry bursts. Single-process (one uvicorn worker), so
    in-process bucket is sufficient.
    """

    def __init__(self, rate_per_sec: float, burst: int | None = None):
        self.rate = rate_per_sec
        self.capacity = burst or max(1, int(rate_per_sec))
        self.tokens = float(self.capacity)
        self.last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self.last
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.last = now
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                # Sleep until we expect to have a token, then re-check
                wait = (1.0 - self.tokens) / self.rate
            await asyncio.sleep(min(wait, 0.5))


# 4 req/sec sustained, burst of 4. Tested to stay under Etherscan's 5 RPS.
_BUCKET = _TokenBucket(rate_per_sec=4.0, burst=4)

# Retry config — transient errors (rate-limit, 5xx, timeout) get retried with
# exponential backoff. Permanent errors (4xx other than 429) bail immediately.
_MAX_RETRIES = 4
_BACKOFF_BASE = 0.8  # seconds, doubled each attempt + jitter


class _RateLimitedError(Exception):
    """Raised when Etherscan returns 'rate limit reached' in the body."""


async def _call(client: httpx.AsyncClient, chain_id: int, params: dict, key: str) -> dict:
    """Make one Etherscan V2 call with retry. Raises on permanent failure."""
    p = {"apikey": key, "chainid": chain_id, **params}
    last_exc: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            await _BUCKET.acquire()
            r = await client.get(ETHERSCAN_BASE, params=p, timeout=15.0)
            if r.status_code == 429:
                raise _RateLimitedError("HTTP 429")
            if 500 <= r.status_code < 600:
                r.raise_for_status()
            r.raise_for_status()
            data = r.json()
            res = data.get("result")
            if isinstance(res, str) and "rate limit" in res.lower():
                raise _RateLimitedError(res)
            if data.get("status") == "0" and isinstance(res, str) and any(
                s in res.lower() for s in ("nodes", "timeout", "unavailable", "busy", "try again")
            ):
                raise _RateLimitedError(res)
            return data
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError,
                httpx.HTTPStatusError, _RateLimitedError) as e:
            last_exc = e
            if attempt == _MAX_RETRIES - 1:
                raise
            delay = _BACKOFF_BASE * (2 ** attempt) + random.uniform(0, 0.4)
            await asyncio.sleep(delay)
        except Exception:
            raise
    if last_exc:
        raise last_exc
    return {}


# Tier-based offsets — primary chains get deeper history, long-tail stays shallow.
TIER_LIMITS = {"primary": 50, "secondary": 30, "tertiary": 20}


class EtherscanV2Provider(ChainProvider):
    slug = "etherscan"

    def __init__(self, api_key_loader):
        self._loader = api_key_loader
        self._key: str | None = None

    def _get_key(self) -> str | None:
        if self._key is None:
            self._key = self._loader()
        return self._key

    async def fetch(self, client, chain, address):
        from ..chain import ChainData, _normalize_erc20, _normalize_nft, _normalize_tx

        cd = ChainData(
            chain=chain.slug,
            label=chain.label,
            symbol=chain.symbol,
            is_testnet=chain.is_testnet,
        )
        key = self._get_key()
        if not key:
            cd.error = "no_etherscan_api_key"
            return cd

        offset = TIER_LIMITS.get(chain.tier, 30)
        sub_errors: list[str] = []

        # --- Balance ---------------------------------------------------------
        try:
            bal = await _call(client, chain.chain_id, {
                "module": "account", "action": "balance",
                "address": address, "tag": "latest",
            }, key)
            if bal.get("status") == "1":
                try:
                    cd.balance = int(bal["result"]) / 1e18
                except (TypeError, ValueError):
                    pass
        except Exception as e:
            sub_errors.append(f"balance:{type(e).__name__}")

        # --- External tx list ------------------------------------------------
        try:
            txs = await _call(client, chain.chain_id, {
                "module": "account", "action": "txlist", "address": address,
                "startblock": 0, "endblock": 99999999,
                "page": 1, "offset": offset, "sort": "desc",
            }, key)
            if txs.get("status") == "1" and isinstance(txs.get("result"), list):
                cd.tx_count = len(txs["result"])
                cd.txs = [_normalize_tx(t, chain.slug) for t in txs["result"]]
        except Exception as e:
            sub_errors.append(f"txlist:{type(e).__name__}")

        # --- Internal tx (incoming ETH from contracts) -----------------------
        # Critical for receive-only wallets: airdrops / bridge withdrawals /
        # contract refunds arrive here, NOT in txlist.
        try:
            itxs = await _call(client, chain.chain_id, {
                "module": "account", "action": "txlistinternal", "address": address,
                "startblock": 0, "endblock": 99999999,
                "page": 1, "offset": offset, "sort": "desc",
            }, key)
            if itxs.get("status") == "1" and isinstance(itxs.get("result"), list):
                cd.internal_tx_count = len(itxs["result"])
        except Exception as e:
            sub_errors.append(f"txlistinternal:{type(e).__name__}")

        # --- ERC20 + NFT (primary mainnets only) ----------------------------
        if chain.tier == "primary" and not chain.is_testnet:
            try:
                erc20 = await _call(client, chain.chain_id, {
                    "module": "account", "action": "tokentx", "address": address,
                    "page": 1, "offset": 50, "sort": "desc",
                }, key)
                if erc20.get("status") == "1" and isinstance(erc20.get("result"), list):
                    cd.erc20_transfers = [_normalize_erc20(t, chain.slug) for t in erc20["result"]]
            except Exception as e:
                sub_errors.append(f"tokentx:{type(e).__name__}")

            try:
                nft = await _call(client, chain.chain_id, {
                    "module": "account", "action": "tokennfttx", "address": address,
                    "page": 1, "offset": 30, "sort": "desc",
                }, key)
                if nft.get("status") == "1" and isinstance(nft.get("result"), list):
                    cd.nft_transfers = [_normalize_nft(t, chain.slug) for t in nft["result"]]
            except Exception as e:
                sub_errors.append(f"tokennfttx:{type(e).__name__}")

        # --- Surface partial / error state ----------------------------------
        if sub_errors:
            cd.partial = True
            cd.error = "; ".join(sub_errors)[:200]
            log.info("etherscan partial fetch %s: %s", chain.slug, cd.error)

        return cd


def install(api_key_loader) -> None:
    """Register the singleton instance with the provided key loader."""
    register(EtherscanV2Provider(api_key_loader))
