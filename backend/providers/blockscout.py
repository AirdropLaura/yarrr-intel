"""Blockscout provider — fallback for chains outside Etherscan V2.

Used when a chain's primary explorer doesn't support Etherscan V2 (some early
testnets, some L2s). Token data is best-effort; we skip ERC20/NFT here because
free Blockscout instances rate-limit hard on tokentx.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from . import ChainProvider, register

log = logging.getLogger("yarrr-tech.providers.blockscout")

UA = {"User-Agent": "Yarrr.Tech/0.5 (+https://yarrr-node.com)"}


async def _call(client: httpx.AsyncClient, base: str, params: dict, retries: int = 1) -> dict:
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


class BlockscoutProvider(ChainProvider):
    slug = "blockscout"

    async def fetch(self, client, chain, address):
        from ..chain import ChainData, _normalize_tx

        cd = ChainData(
            chain=chain.slug,
            label=chain.label,
            symbol=chain.symbol,
            is_testnet=chain.is_testnet,
        )
        if not chain.blockscout_base:
            cd.error = "no_blockscout_base_url"
            return cd

        try:
            bal = await _call(client, chain.blockscout_base, {
                "module": "account", "action": "balance", "address": address,
            })
            if bal.get("status") == "1":
                try:
                    cd.balance = int(bal["result"]) / 1e18
                except (TypeError, ValueError):
                    pass

            txs = await _call(client, chain.blockscout_base, {
                "module": "account", "action": "txlist", "address": address,
                "page": 1, "offset": 30, "sort": "desc",
            })
            if txs.get("status") == "1" and isinstance(txs.get("result"), list):
                cd.tx_count = len(txs["result"])
                cd.txs = [_normalize_tx(t, chain.slug) for t in txs["result"]]
        except Exception as e:
            cd.error = f"{type(e).__name__}: {str(e)[:120]}"
            log.debug("blockscout fetch failed for %s: %s", chain.slug, cd.error)
        return cd


def install() -> None:
    register(BlockscoutProvider())
