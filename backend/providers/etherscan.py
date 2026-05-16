"""Etherscan V2 provider — multichain via `chainid` parameter.

One API key (free tier 5 calls/sec) covers ~16 mainnets + testnets. We respect
the rate limit with a process-wide semaphore and fail soft on rate-limit
responses (Etherscan signals via `result: "Max rate limit reached"`).
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from . import ChainProvider, register

log = logging.getLogger("yarrr-tech.providers.etherscan")

ETHERSCAN_BASE = "https://api.etherscan.io/v2/api"

# Free tier: 5 RPS shared. Cap concurrency at 4 to leave headroom for retries
# and stay under the ceiling.
_LOCK = asyncio.Semaphore(4)


async def _call(client: httpx.AsyncClient, chain_id: int, params: dict, key: str) -> dict:
    p = {"apikey": key, "chainid": chain_id, **params}
    async with _LOCK:
        r = await client.get(ETHERSCAN_BASE, params=p, timeout=15.0)
    r.raise_for_status()
    data = r.json()
    if isinstance(data.get("result"), str) and "rate limit" in data["result"].lower():
        await asyncio.sleep(1.0)
        async with _LOCK:
            r = await client.get(ETHERSCAN_BASE, params=p, timeout=15.0)
        r.raise_for_status()
        data = r.json()
    return data


# Tier-based offsets — primary chains get deeper history, long-tail stays shallow.
TIER_LIMITS = {"primary": 50, "secondary": 30, "tertiary": 20}


class EtherscanV2Provider(ChainProvider):
    slug = "etherscan"

    def __init__(self, api_key_loader):
        # Lazy load — avoids touching the filesystem at import time.
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

            txs = await _call(client, chain.chain_id, {
                "module": "account", "action": "txlist", "address": address,
                "startblock": 0, "endblock": 99999999,
                "page": 1, "offset": offset, "sort": "desc",
            }, key)
            if txs.get("status") == "1" and isinstance(txs.get("result"), list):
                cd.tx_count = len(txs["result"])
                cd.txs = [_normalize_tx(t, chain.slug) for t in txs["result"]]

            # ERC20 + NFT only on primary tier mainnets — keeps fan-out + rate
            # limits in check.
            if chain.tier == "primary" and not chain.is_testnet:
                erc20 = await _call(client, chain.chain_id, {
                    "module": "account", "action": "tokentx", "address": address,
                    "page": 1, "offset": 50, "sort": "desc",
                }, key)
                if erc20.get("status") == "1" and isinstance(erc20.get("result"), list):
                    cd.erc20_transfers = [_normalize_erc20(t, chain.slug) for t in erc20["result"]]

                nft = await _call(client, chain.chain_id, {
                    "module": "account", "action": "tokennfttx", "address": address,
                    "page": 1, "offset": 30, "sort": "desc",
                }, key)
                if nft.get("status") == "1" and isinstance(nft.get("result"), list):
                    cd.nft_transfers = [_normalize_nft(t, chain.slug) for t in nft["result"]]
        except Exception as e:
            cd.error = f"{type(e).__name__}: {str(e)[:120]}"
            log.debug("etherscan fetch failed for %s: %s", chain.slug, cd.error)
        return cd


def install(api_key_loader) -> None:
    """Register the singleton instance with the provided key loader."""
    register(EtherscanV2Provider(api_key_loader))
