"""Multichain onchain data fetcher.

Strategy: Etherscan V2 (single API key, multi-chain by chain_id) for the
broadest coverage, with Blockscout as a fallback for chains outside V2.

Layer 1 of the 3-layer pipeline. Breadth-first: we'd rather know a wallet
touched 12 chains shallowly than know 5 chains in deep detail. The profiler
turns shallow signal into sharp behavioral inference.

Per chain we collect:
- Native balance
- Last N normal transactions (txlist) — reveals contract interactions
- Failed/revert flag, method name, counterparty, gas — keeps profiler signals
  rich without ERC20/NFT ingestion (those land in Phase 2).
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Iterable

import httpx

log = logging.getLogger("yarrr-intel.chain")


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
    provider: str           # "etherscan" or "blockscout"
    chain_id: int | None = None
    blockscout_base: str | None = None
    is_testnet: bool = False
    # `tier` controls per-call tx fetch budget. mainnet_primary chains get
    # deeper history; tertiary chains stay shallow to keep total latency low.
    tier: str = "primary"   # primary | secondary | tertiary


# ---------------------------------------------------------------------------
# Chain registry — Etherscan V2 covers all these with one API key.
# Reference: https://docs.etherscan.io/etherscan-v2/getting-started/v2-quickstart
#
# Adding a chain = adding one row here. Profiler is chain-agnostic.
# ---------------------------------------------------------------------------
MAINNETS: list[Chain] = [
    # Tier 1 — primary EVM hubs
    Chain("ethereum",  "Ethereum",   "ETH",   "etherscan", chain_id=1,         tier="primary"),
    Chain("base",      "Base",       "ETH",   "etherscan", chain_id=8453,      tier="primary"),
    Chain("arbitrum",  "Arbitrum",   "ETH",   "etherscan", chain_id=42161,     tier="primary"),
    Chain("optimism",  "Optimism",   "ETH",   "etherscan", chain_id=10,        tier="primary"),
    Chain("polygon",   "Polygon",    "POL",   "etherscan", chain_id=137,       tier="primary"),
    # Tier 2 — major secondary chains
    Chain("bsc",       "BNB Chain",  "BNB",   "etherscan", chain_id=56,        tier="secondary"),
    Chain("avalanche", "Avalanche",  "AVAX",  "etherscan", chain_id=43114,     tier="secondary"),
    Chain("linea",     "Linea",      "ETH",   "etherscan", chain_id=59144,     tier="secondary"),
    Chain("scroll",    "Scroll",     "ETH",   "etherscan", chain_id=534352,    tier="secondary"),
    Chain("blast",     "Blast",      "ETH",   "etherscan", chain_id=81457,     tier="secondary"),
    # Tier 3 — long tail
    Chain("mantle",    "Mantle",     "MNT",   "etherscan", chain_id=5000,      tier="tertiary"),
    Chain("worldchain","World Chain","ETH",   "etherscan", chain_id=480,       tier="tertiary"),
    Chain("opbnb",     "opBNB",      "BNB",   "etherscan", chain_id=204,       tier="tertiary"),
    Chain("gnosis",    "Gnosis",     "xDAI",  "etherscan", chain_id=100,       tier="tertiary"),
    Chain("celo",      "Celo",       "CELO",  "etherscan", chain_id=42220,     tier="tertiary"),
    Chain("zksync",    "zkSync Era", "ETH",   "etherscan", chain_id=324,       tier="tertiary"),
    # Tier 3 — emerging ecosystems (2025+ launches)
    Chain("berachain", "Berachain",  "BERA",  "etherscan", chain_id=80094,     tier="tertiary"),
    Chain("monad",     "Monad",      "MON",   "etherscan", chain_id=143,       tier="tertiary"),
    Chain("sonic",     "Sonic",      "S",     "etherscan", chain_id=146,       tier="tertiary"),
    Chain("abstract",  "Abstract",   "ETH",   "etherscan", chain_id=2741,      tier="tertiary"),
    Chain("taiko",     "Taiko",      "ETH",   "etherscan", chain_id=167000,    tier="tertiary"),
    Chain("fraxtal",   "Fraxtal",    "frxETH","etherscan", chain_id=252,       tier="tertiary"),
]

TESTNETS: list[Chain] = [
    # Active testnet ecosystems — major airdrop farming territory.
    Chain("sepolia",         "Sepolia",         "ETH",  "etherscan", chain_id=11155111,  is_testnet=True, tier="secondary"),
    Chain("holesky",         "Holesky",         "ETH",  "etherscan", chain_id=17000,     is_testnet=True, tier="tertiary"),
    Chain("base-sepolia",    "Base Sepolia",    "ETH",  "etherscan", chain_id=84532,     is_testnet=True, tier="secondary"),
    Chain("arbitrum-sepolia","Arbitrum Sepolia","ETH",  "etherscan", chain_id=421614,    is_testnet=True, tier="secondary"),
    Chain("optimism-sepolia","Optimism Sepolia","ETH",  "etherscan", chain_id=11155420,  is_testnet=True, tier="tertiary"),
    Chain("polygon-amoy",    "Polygon Amoy",    "POL",  "etherscan", chain_id=80002,     is_testnet=True, tier="tertiary"),
    Chain("bsc-testnet",     "BSC Testnet",     "BNB",  "etherscan", chain_id=97,        is_testnet=True, tier="tertiary"),
    Chain("linea-sepolia",   "Linea Sepolia",   "ETH",  "etherscan", chain_id=59141,     is_testnet=True, tier="tertiary"),
    Chain("scroll-sepolia",  "Scroll Sepolia",  "ETH",  "etherscan", chain_id=534351,    is_testnet=True, tier="tertiary"),
    Chain("blast-sepolia",   "Blast Sepolia",   "ETH",  "etherscan", chain_id=168587773, is_testnet=True, tier="tertiary"),
    # Emerging ecosystem testnets (heavy airdrop farming territory in 2025-2026)
    Chain("berachain-bepolia","Berachain Bepolia","BERA","etherscan", chain_id=80069,     is_testnet=True, tier="tertiary"),
    Chain("monad-testnet",   "Monad Testnet",   "MON",  "etherscan", chain_id=10143,     is_testnet=True, tier="tertiary"),
    Chain("sonic-testnet",   "Sonic Testnet",   "S",    "etherscan", chain_id=14601,     is_testnet=True, tier="tertiary"),
    Chain("abstract-sepolia","Abstract Sepolia","ETH",  "etherscan", chain_id=11124,     is_testnet=True, tier="tertiary"),
    Chain("mantle-sepolia",  "Mantle Sepolia",  "MNT",  "etherscan", chain_id=5003,      is_testnet=True, tier="tertiary"),
]

# Convenience: tier → max txlist offset (caps fetch cost on long-tail chains).
_TIER_LIMITS = {"primary": 50, "secondary": 30, "tertiary": 20}

# Default scan profile: all mainnets + all major testnets.
ALL_CHAINS: list[Chain] = MAINNETS + TESTNETS

# Backward-compat alias.
CHAINS: list[Chain] = ALL_CHAINS

# Slug → Chain lookup; built once at module load.
_CHAIN_INDEX: dict[str, Chain] = {c.slug: c for c in ALL_CHAINS}


def get_chain(slug: str) -> Chain | None:
    """Look up a Chain by slug. Used by contract_names resolver."""
    return _CHAIN_INDEX.get(slug)


@dataclass
class TokenTransfer:
    """ERC20 transfer normalized across providers."""
    chain: str
    ts: int
    hash: str
    from_addr: str
    to_addr: str
    contract: str
    symbol: str
    name: str
    amount: float       # human-readable, decimals applied
    decimals: int


@dataclass
class NFTTransfer:
    """ERC721/ERC1155 transfer normalized across providers."""
    chain: str
    ts: int
    hash: str
    from_addr: str
    to_addr: str
    contract: str
    symbol: str
    name: str
    token_id: str


@dataclass
class ChainData:
    chain: str
    label: str
    symbol: str
    is_testnet: bool = False
    balance: float = 0.0
    tx_count: int = 0
    txs: list[dict] = field(default_factory=list)
    erc20_transfers: list[TokenTransfer] = field(default_factory=list)
    nft_transfers: list[NFTTransfer] = field(default_factory=list)
    error: str | None = None


_UA = {"User-Agent": "Yarrr.Tech/0.4 (+https://yarrr-node.com)"}
_ETHERSCAN_BASE = "https://api.etherscan.io/v2/api"

# Etherscan free tier: 5 calls/sec across all chains. We cap concurrency at 4
# to leave headroom for retry bursts and stay under the rate limit.
_ETHERSCAN_LOCK = asyncio.Semaphore(4)


async def _es_call(client: httpx.AsyncClient, chain_id: int, params: dict, key: str) -> dict:
    p = {"apikey": key, "chainid": chain_id, **params}
    async with _ETHERSCAN_LOCK:
        r = await client.get(_ETHERSCAN_BASE, params=p, timeout=15.0)
    r.raise_for_status()
    data = r.json()
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
    """LEGACY shim — delegates to the EtherscanV2Provider in providers/.

    Kept so tests / external callers that imported the old name still work
    until they migrate to `dispatch_fetch`.
    """
    from .providers import get
    p = get("etherscan")
    if p is None:
        cd = ChainData(chain=chain.slug, label=chain.label, symbol=chain.symbol, is_testnet=chain.is_testnet)
        cd.error = "etherscan provider not registered"
        return cd
    return await p.fetch(client, chain, address)


async def _fetch_blockscout(client: httpx.AsyncClient, chain: Chain, address: str) -> ChainData:
    """LEGACY shim — delegates to the BlockscoutProvider in providers/."""
    from .providers import get
    p = get("blockscout")
    if p is None:
        cd = ChainData(chain=chain.slug, label=chain.label, symbol=chain.symbol, is_testnet=chain.is_testnet)
        cd.error = "blockscout provider not registered"
        return cd
    return await p.fetch(client, chain, address)


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
        "gas_price": int(t.get("gasPrice", 0) or 0),
    }


def _normalize_erc20(t: dict, chain: str) -> TokenTransfer:
    """Etherscan tokentx shape: from, to, contractAddress, tokenSymbol,
    tokenName, value (raw int), tokenDecimal, timeStamp, hash."""
    try:
        ts = int(t.get("timeStamp", 0) or 0)
        decimals = int(t.get("tokenDecimal", 18) or 18)
        raw = int(t.get("value", 0) or 0)
        amount = raw / (10 ** decimals) if decimals else float(raw)
    except (TypeError, ValueError):
        ts, decimals, amount = 0, 18, 0.0
    return TokenTransfer(
        chain=chain,
        ts=ts,
        hash=t.get("hash", ""),
        from_addr=(t.get("from") or "").lower(),
        to_addr=(t.get("to") or "").lower(),
        contract=(t.get("contractAddress") or "").lower(),
        symbol=t.get("tokenSymbol", "")[:24],
        name=t.get("tokenName", "")[:60],
        amount=amount,
        decimals=decimals,
    )


def _normalize_nft(t: dict, chain: str) -> NFTTransfer:
    """Etherscan tokennfttx shape: from, to, contractAddress, tokenID,
    tokenName, tokenSymbol, timeStamp, hash."""
    try:
        ts = int(t.get("timeStamp", 0) or 0)
    except (TypeError, ValueError):
        ts = 0
    return NFTTransfer(
        chain=chain,
        ts=ts,
        hash=t.get("hash", ""),
        from_addr=(t.get("from") or "").lower(),
        to_addr=(t.get("to") or "").lower(),
        contract=(t.get("contractAddress") or "").lower(),
        symbol=t.get("tokenSymbol", "")[:24],
        name=t.get("tokenName", "")[:80],
        token_id=str(t.get("tokenID", ""))[:32],
    )


async def fetch_wallet_all_chains(
    address: str,
    chains: Iterable[Chain] | None = None,
) -> list[ChainData]:
    """Parallel fetch across the chain registry.

    Dispatches each chain to its registered provider (etherscan, blockscout,
    future: berachain, starknet). Each provider handles its own errors —
    one chain failing does not break the others.

    `chains` defaults to ALL_CHAINS (mainnets + testnets). Pass a custom subset
    for shallow scans or specific chain investigations.
    """
    from .providers import get as get_provider

    address = address.lower()
    chains = list(chains) if chains is not None else ALL_CHAINS
    timeout = httpx.Timeout(25.0, connect=8.0)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        tasks = []
        for c in chains:
            provider = get_provider(c.provider)
            if provider is None:
                # Unregistered provider — skip silently. Logged at debug so we
                # can spot misconfigured chain rows.
                log.debug("no provider registered for %s (slug=%s)", c.slug, c.provider)
                continue
            tasks.append(provider.fetch(client, c, address))
        results = await asyncio.gather(*tasks, return_exceptions=True)

    out: list[ChainData] = []
    for r in results:
        if isinstance(r, Exception):
            log.debug("chain fetch raised: %s", r)
            continue
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# Provider auto-registration on first import. Order matters only for clarity.
# ---------------------------------------------------------------------------
def _install_default_providers() -> None:
    from .providers.blockscout import install as install_bs
    from .providers.etherscan import install as install_es
    from .providers.routescan import install as install_rs

    install_es(_load_etherscan_key)
    install_bs()
    install_rs()


_install_default_providers()
