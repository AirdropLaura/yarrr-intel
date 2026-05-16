"""Provider abstraction for chain data sources.

Why this layer exists:
- Etherscan V2 covers 16+ EVM mainnets + testnets with one API key, but it
  doesn't cover everything: Berachain, Monad, Soneium, Abstract, Hyperliquid
  use their own block explorers or RPC interfaces. Adding each one as a
  one-off branch in `chain.py` rots fast.
- A `Provider` protocol means: define the chain → register the right provider
  class → done. Profiler doesn't care where the bytes came from.

Contract:
- Each provider implements `fetch(client, chain, address)` returning a
  populated `ChainData` instance. Providers normalize their own quirks into
  the shared `_normalize_tx`, `_normalize_erc20`, `_normalize_nft` helpers.
- Providers MUST handle their own errors and return `ChainData(error="...")`
  rather than raising. This way one chain's outage doesn't break the whole
  multichain fetch.

To add a new chain:
    1. Create or reuse a `Provider` subclass.
    2. Register a `Chain` row in `chain.py` with `provider="<slug>"`.
    3. The dispatcher in `fetch_wallet_all_chains` picks the right provider.

Currently shipped:
- `EtherscanV2Provider` — multi-chain via single API key + chain_id
- `BlockscoutProvider` — for chains outside Etherscan V2 (limited tx data)

Phase 3 (planned):
- `BerachainProvider` (Routescan / berascan)
- `StarknetProvider` (voyager API, non-EVM)
"""
from __future__ import annotations

import abc
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from .chain import Chain, ChainData


class ChainProvider(abc.ABC):
    """Abstract base. One instance per provider class — stateless across calls."""

    slug: str = "abstract"

    @abc.abstractmethod
    async def fetch(
        self,
        client: httpx.AsyncClient,
        chain: "Chain",
        address: str,
    ) -> "ChainData":
        """Fetch native balance + tx history (and tokens if supported) for `address` on `chain`.

        MUST NOT raise on per-chain failure — set `cd.error` instead.
        """


# Provider registry — slug → instance. `chain.py` populates this on import.
REGISTRY: dict[str, ChainProvider] = {}


def register(provider: ChainProvider) -> None:
    REGISTRY[provider.slug] = provider


def get(slug: str) -> ChainProvider | None:
    return REGISTRY.get(slug)
