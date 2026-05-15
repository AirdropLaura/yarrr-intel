"""Multichain onchain data fetcher — MVP scope.

Strategy: hybrid free-tier coverage.
- Etherscan V2 (1 key) → Ethereum, Polygon, Arbitrum
- Blockscout (free, public) → Base, Optimism

For each chain we fetch only:
- Native balance
- Last 50 normal transactions (txlist) — reveals contract interactions

We deliberately skip ERC20 tokentx in MVP because:
1. Most behavior signal is already in txlist (counterparty contracts).
2. Free tier Blockscout endpoints time out frequently on tokentx.
3. Profiler can classify counterparty contracts via known-address heuristics.

If the user demand justifies it, we can add tokentx back as a paid-tier upgrade.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Iterable

import httpx


def _load_etherscan_key() -> str | None:
    key = os.getenv("ETHERSCAN_API_KEY")
    if key:
        return key
    cred = os.path.expanduser("~/.hermes/credentials/etherscan.env")
    if os.path.exists(cred):
        for line in open(cred):
            line = line.strip()
            if line.startswith("ETHERSCAN_API_KEY="):
                return line.split("=", 1)[1].strip()
    return None


@dataclass
class Chain:
    slug: str
    label: str
    symbol: str
    provider: str  # "etherscan" or "blockscout"
    chain_id: int | None = None
    blockscout_base: str | None = None


CHAINS: list[Chain] = [
    Chain("ethereum", "Ethereum",  "ETH",   "etherscan",  chain_id=1),
    Chain("polygon",  "Polygon",   "MATIC", "etherscan",  chain_id=137),
    Chain("arbitrum", "Arbitrum",  "ETH",   "etherscan",  chain_id=42161),
    Chain("base",     "Base",      "ETH",   "blockscout", blockscout_base="https://base.blockscout.com/api"),
    Chain("optimism", "Optimism",  "ETH",   "blockscout", blockscout_base="https://explorer.optimism.io/api"),
]


@dataclass
class ChainData:
    chain: str
    label: str
    symbol: str
    balance: float = 0.0
    tx_count: int = 0
    txs: list[dict] = field(default_factory=list)
    error: str | None = None


_UA = {"User-Agent": "Yarrr.Intel/0.1 (+https://yarrr-node.com)"}
_ETHERSCAN_BASE = "https://api.etherscan.io/v2/api"
# Etherscan free tier: 5 calls/sec across all chains. Allow 3 concurrent in flight
# (each call takes 200-500ms on average, so ~6-15 rps cap = under the 5/sec ceiling).
_ETHERSCAN_LOCK = asyncio.Semaphore(3)


async def _es_call(client: httpx.AsyncClient, chain_id: int, params: dict, key: str) -> dict:
    p = {"apikey": key, "chainid": chain_id, **params}
    async with _ETHERSCAN_LOCK:
        r = await client.get(_ETHERSCAN_BASE, params=p, timeout=15.0)
    r.raise_for_status()
    data = r.json()
    # Etherscan signals throttling via {"status":"0","message":"NOTOK","result":"Max rate limit reached"}
    if isinstance(data.get("result"), str) and "rate limit" in data["result"].lower():
        await asyncio.sleep(1.0)
        async with _ETHERSCAN_LOCK:
            r = await client.get(_ETHERSCAN_BASE, params=p, timeout=15.0)
        r.raise_for_status()
        data = r.json()
    return data


async def _bs_call(client: httpx.AsyncClient, base: str, params: dict, retries: int = 1) -> dict:
    last = None
    for attempt in range(retries + 1):
        try:
            r = await client.get(base, params=params, headers=_UA, timeout=12.0)
            r.raise_for_status()
            return r.json()
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError) as e:
            last = e
            if attempt < retries:
                await asyncio.sleep(0.6)
                continue
            raise


async def _fetch_etherscan(client: httpx.AsyncClient, chain: Chain, address: str, key: str) -> ChainData:
    cd = ChainData(chain=chain.slug, label=chain.label, symbol=chain.symbol)
    try:
        bal = await _es_call(client, chain.chain_id, {"module": "account", "action": "balance", "address": address, "tag": "latest"}, key)
        if bal.get("status") == "1":
            try:
                cd.balance = int(bal["result"]) / 1e18
            except (TypeError, ValueError):
                pass

        txs = await _es_call(client, chain.chain_id, {
            "module": "account", "action": "txlist", "address": address,
            "startblock": 0, "endblock": 99999999, "page": 1, "offset": 50, "sort": "desc",
        }, key)
        if txs.get("status") == "1" and isinstance(txs.get("result"), list):
            cd.tx_count = len(txs["result"])
            cd.txs = [_normalize_tx(t, chain.slug) for t in txs["result"]]
    except Exception as e:
        cd.error = f"{type(e).__name__}: {str(e)[:120]}"
    return cd


async def _fetch_blockscout(client: httpx.AsyncClient, chain: Chain, address: str) -> ChainData:
    cd = ChainData(chain=chain.slug, label=chain.label, symbol=chain.symbol)
    try:
        bal = await _bs_call(client, chain.blockscout_base, {"module": "account", "action": "balance", "address": address})
        if bal.get("status") == "1":
            try:
                cd.balance = int(bal["result"]) / 1e18
            except (TypeError, ValueError):
                pass

        txs = await _bs_call(client, chain.blockscout_base, {
            "module": "account", "action": "txlist", "address": address,
            "page": 1, "offset": 50, "sort": "desc",
        })
        if txs.get("status") == "1" and isinstance(txs.get("result"), list):
            cd.tx_count = len(txs["result"])
            cd.txs = [_normalize_tx(t, chain.slug) for t in txs["result"]]
    except Exception as e:
        cd.error = f"{type(e).__name__}: {str(e)[:120]}"
    return cd


def _normalize_tx(t: dict, chain: str) -> dict:
    """Etherscan & Blockscout share a similar txlist shape."""
    try:
        ts = int(t.get("timeStamp", 0) or 0)
        value_wei = int(t.get("value", 0) or 0)
    except (TypeError, ValueError):
        ts, value_wei = 0, 0
    return {
        "chain": chain,
        "hash": t.get("hash", ""),
        "ts": ts,
        "from": (t.get("from") or "").lower(),
        "to": (t.get("to") or "").lower(),
        "value_eth": round(value_wei / 1e18, 6),
        "method": (t.get("functionName") or t.get("methodId") or "").split("(")[0],
        "is_error": str(t.get("isError", "0")) == "1",
        "gas_used": int(t.get("gasUsed", 0) or 0),
    }


async def fetch_wallet_all_chains(address: str, chains: Iterable[Chain] = None) -> list[ChainData]:
    address = address.lower()
    chains = list(chains) if chains is not None else CHAINS
    key = _load_etherscan_key()
    timeout = httpx.Timeout(25.0, connect=8.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        tasks = []
        for c in chains:
            if c.provider == "etherscan":
                if not key:
                    continue
                tasks.append(_fetch_etherscan(client, c, address, key))
            else:
                tasks.append(_fetch_blockscout(client, c, address))
        results = await asyncio.gather(*tasks, return_exceptions=True)
    out: list[ChainData] = []
    for r in results:
        if isinstance(r, Exception):
            continue
        out.append(r)
    return out
