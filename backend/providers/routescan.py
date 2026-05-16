"""Routescan provider — fallback for EVM chains outside Etherscan V2.

Routescan covers Avalanche L1 + dozens of subnets (Dexalot, Beam, Numbers,
DeFi Kingdoms, Lamina1, etc.) plus a few standalone chains. Their API is
free, public, no key required.

API base: `https://api.routescan.io/v2/network/{network}/evm/{chain_id}/etherscan/api`
- network = "mainnet" or "testnet"
- chain_id = standard EIP-155 id

Routescan exposes an Etherscan-V1-compatible API at the path above, which
means we reuse our existing `_normalize_tx`/`_normalize_erc20`/`_normalize_nft`
helpers without translation. That keeps the provider tiny.

Currently registered as a provider but no chain in `chain.py` uses it yet —
the framework is ready and any chain whose explorer is on Routescan can be
added with one row in the chain registry.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from . import ChainProvider, register

log = logging.getLogger("yarrr-tech.providers.routescan")

ROUTESCAN_BASE = "https://api.routescan.io/v2/network"
UA = {"User-Agent": "Yarrr.Tech/0.8 (+https://yarrr-node.com)"}

# Process-wide concurrency limit — be polite to the public API.
_SEM = asyncio.Semaphore(4)


async def _call(client: httpx.AsyncClient, base: str, params: dict, retries: int = 1) -> dict:
    """Etherscan-shape call with one retry on transient errors."""
    for attempt in range(retries + 1):
        try:
            r = await client.get(base, params=params, headers=UA, timeout=12.0)
            r.raise_for_status()
            return r.json()
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError):
            if attempt < retries:
                await asyncio.sleep(0.6)
                continue
            raise


class RoutescanProvider(ChainProvider):
    """Routescan multichain provider — Etherscan-compatible API surface."""
    slug = "routescan"

    async def fetch(self, client, chain, address):
        from ..chain import ChainData, _normalize_erc20, _normalize_nft, _normalize_tx

        cd = ChainData(
            chain=chain.slug,
            label=chain.label,
            symbol=chain.symbol,
            is_testnet=chain.is_testnet,
        )
        network = "testnet" if chain.is_testnet else "mainnet"
        base = f"{ROUTESCAN_BASE}/{network}/evm/{chain.chain_id}/etherscan/api"

        async with _SEM:
            try:
                # Native balance
                bal = await _call(client, base, {
                    "module": "account", "action": "balance", "address": address,
                })
                if bal.get("status") == "1":
                    try:
                        cd.balance = int(bal["result"]) / 1e18
                    except (TypeError, ValueError):
                        pass

                # Transactions
                txs = await _call(client, base, {
                    "module": "account", "action": "txlist", "address": address,
                    "page": 1, "offset": 50, "sort": "desc",
                })
                if txs.get("status") == "1" and isinstance(txs.get("result"), list):
                    cd.tx_count = len(txs["result"])
                    cd.txs = [_normalize_tx(t, chain.slug) for t in txs["result"]]

                # ERC20 + NFT only on primary tier — token endpoints are heavier
                if chain.tier == "primary":
                    try:
                        erc20 = await _call(client, base, {
                            "module": "account", "action": "tokentx", "address": address,
                            "page": 1, "offset": 50, "sort": "desc",
                        })
                        if erc20.get("status") == "1" and isinstance(erc20.get("result"), list):
                            cd.erc20 = [_normalize_erc20(t, chain.slug) for t in erc20["result"]]
                    except Exception as e:
                        log.debug("routescan erc20 failed for %s: %s", chain.slug, e)

                    try:
                        nfts = await _call(client, base, {
                            "module": "account", "action": "tokennfttx", "address": address,
                            "page": 1, "offset": 50, "sort": "desc",
                        })
                        if nfts.get("status") == "1" and isinstance(nfts.get("result"), list):
                            cd.nfts = [_normalize_nft(t, chain.slug) for t in nfts["result"]]
                    except Exception as e:
                        log.debug("routescan nft failed for %s: %s", chain.slug, e)
            except Exception as e:
                cd.error = f"{type(e).__name__}: {str(e)[:120]}"
                log.debug("routescan fetch failed for %s: %s", chain.slug, cd.error)
        return cd


def install() -> None:
    register(RoutescanProvider())
