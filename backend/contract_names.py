"""Dynamic contract name resolver — Layer 1.5 between raw fetch and profiler.

Why this exists:
The original profiler fell back to "Unknown contract" for any address not in
the hardcoded KNOWN_CONTRACTS dict. With 37 chains and millions of contracts,
that fallback hit way too often and made outputs look uninformed.

Resolution strategy (each step short-circuits if it finds a name):
1. Curated KNOWN_CONTRACTS — fast, hand-labeled, beats all
2. SQLite cache (`contract_names` table) — verified-once-cached-forever
3. ERC20 token transfers — if wallet transferred a token through this address
   we already know the token's name+symbol from `tokentx` API response
4. NFT collection transfers — same, from `tokennfttx`
5. Etherscan `getsourcecode` API — verified contracts return ContractName
6. Heuristic on transaction shape — known router selectors / proxy patterns
7. Fallback "Unknown contract"

The cache table is small (~30 bytes per row × ~10k contracts = ~300KB) and
read-mostly, so we keep it in the same SQLite as snapshots.

The lookup is async and batched — given a list of unresolved addresses on a
specific chain, we issue ONE concurrent burst of API calls (with semaphore)
and write all results to the cache in a single transaction.
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from dataclasses import dataclass

import httpx

from .persistence import _connect

log = logging.getLogger("yarrr-tech.contract_names")

# Etherscan V2 free tier is 5 req/sec — share the budget across all of
# yarrr-intel's calls. We use a small semaphore to be polite.
_RESOLVER_SEM = asyncio.Semaphore(3)

# How long a cached name is considered fresh. Verified contracts don't get
# re-deployed, so we use a long TTL. Negative results (unknown) are cached
# briefly so we don't keep hammering the API.
TTL_FOUND = 30 * 86400          # 30 days
TTL_NOT_FOUND = 6 * 3600        # 6 hours


def init_contract_names_table() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS contract_names (
                chain         TEXT NOT NULL,
                address       TEXT NOT NULL,
                name          TEXT,
                category      TEXT,
                source        TEXT NOT NULL,    -- known / token / nft / etherscan / heuristic
                resolved_at   INTEGER NOT NULL,
                PRIMARY KEY (chain, address)
            )
            """
        )
        conn.commit()


@dataclass
class ContractIdentity:
    address: str
    chain: str
    name: str | None
    category: str
    source: str

    def is_unknown(self) -> bool:
        return self.name is None or self.category == "unknown"


def _now() -> int:
    return int(time.time())


def lookup_cache(chain: str, address: str) -> ContractIdentity | None:
    """Return cached identity if fresh; None otherwise (caller should resolve)."""
    addr = address.lower()
    with _connect() as conn:
        row = conn.execute(
            "SELECT name, category, source, resolved_at FROM contract_names WHERE chain = ? AND address = ?",
            (chain, addr),
        ).fetchone()
    if not row:
        return None

    age = _now() - int(row["resolved_at"])
    is_known = bool(row["name"])
    ttl = TTL_FOUND if is_known else TTL_NOT_FOUND
    if age > ttl:
        return None

    return ContractIdentity(
        address=addr,
        chain=chain,
        name=row["name"],
        category=row["category"] or "unknown",
        source=row["source"],
    )


def store_cache(chain: str, address: str, name: str | None, category: str, source: str) -> None:
    addr = address.lower()
    try:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO contract_names (chain, address, name, category, source, resolved_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(chain, address) DO UPDATE SET
                    name = excluded.name,
                    category = excluded.category,
                    source = excluded.source,
                    resolved_at = excluded.resolved_at
                """,
                (chain, addr, name, category, source, _now()),
            )
            conn.commit()
    except sqlite3.Error as e:
        log.debug("store_cache failed: %s", e)


# ---------------------------------------------------------------------------
# Source 3: ERC20 / NFT transfer enrichment
# ---------------------------------------------------------------------------

def harvest_token_names(chain_data) -> dict[str, tuple[str, str]]:
    """Extract address → (name, category) from ERC20 + NFT transfer rows.

    Returns: {address_lc: (display_name, category)} where category is
    "token" or "nft_collection".
    """
    found: dict[str, tuple[str, str]] = {}
    for tt in (getattr(chain_data, "erc20_transfers", None) or []):
        addr = (getattr(tt, "contract", "") or "").lower()
        if not addr:
            continue
        name = (getattr(tt, "name", "") or "").strip()
        symbol = (getattr(tt, "symbol", "") or "").strip()
        if name and symbol:
            display = f"{name} ({symbol})"
        else:
            display = name or symbol
        if display:
            found[addr] = (display[:64], "token")

    for nt in (getattr(chain_data, "nft_transfers", None) or []):
        addr = (getattr(nt, "contract", "") or "").lower()
        if not addr or addr in found:
            continue
        name = (getattr(nt, "name", "") or "").strip()
        symbol = (getattr(nt, "symbol", "") or "").strip()
        if name:
            display = f"{name} NFT" if not symbol else f"{name} ({symbol})"
            found[addr] = (display[:64], "nft_collection")

    return found


# ---------------------------------------------------------------------------
# Source 5: Etherscan getsourcecode
# ---------------------------------------------------------------------------

async def _fetch_etherscan_name(
    client: httpx.AsyncClient,
    chain_id: int,
    address: str,
    api_key: str,
) -> tuple[str, str] | None:
    """Returns (ContractName, category_hint) or None.

    Etherscan V2 unified endpoint: https://api.etherscan.io/v2/api?chainid=…
    Action: getsourcecode returns an array; ContractName is the verified name
    (e.g. "UniswapV3Router", "GnosisSafe", "Multicall3"). Empty string means
    not verified.
    """
    params = {
        "chainid": chain_id,
        "module": "contract",
        "action": "getsourcecode",
        "address": address,
        "apikey": api_key,
    }
    try:
        async with _RESOLVER_SEM:
            r = await client.get(
                "https://api.etherscan.io/v2/api",
                params=params,
                timeout=10,
            )
        if r.status_code != 200:
            return None
        body = r.json()
        if body.get("status") != "1":
            return None
        result = body.get("result") or []
        if not result:
            return None
        name = (result[0].get("ContractName") or "").strip()
        if not name:
            return None
        # Heuristic category from the name
        lower = name.lower()
        if any(k in lower for k in ("router", "swap", "pool", "pair")):
            cat = "swap"
        elif any(k in lower for k in ("bridge", "messenger", "portal", "relay")):
            cat = "bridge"
        elif any(k in lower for k in ("safe", "multisig", "wallet")):
            cat = "wallet"
        elif any(k in lower for k in ("erc721", "nft", "collection")):
            cat = "nft"
        elif "permit" in lower or "approve" in lower:
            cat = "approval"
        else:
            cat = "verified"
        return (name, cat)
    except (httpx.HTTPError, ValueError, KeyError) as e:
        log.debug("etherscan name lookup failed for %s on chain %s: %s",
                  address, chain_id, e)
        return None


# ---------------------------------------------------------------------------
# Source 6: Selector heuristic
# ---------------------------------------------------------------------------

# Recognized first-4-bytes (function selectors) → (name, category).
# These are universal — same selector means same function across chains.
SELECTOR_HINTS: dict[str, tuple[str, str]] = {
    "0x38ed1739": ("UniV2 swapExactTokensForTokens", "swap"),
    "0x18cbafe5": ("UniV2 swapExactTokensForETH", "swap"),
    "0x7ff36ab5": ("UniV2 swapExactETHForTokens", "swap"),
    "0x414bf389": ("UniV3 exactInputSingle", "swap"),
    "0xc04b8d59": ("UniV3 exactInput", "swap"),
    "0xac9650d8": ("Multicall", "batch"),
    "0x5ae401dc": ("Multicall (deadline)", "batch"),
    "0xa9059cbb": ("ERC20 transfer", "transfer"),
    "0x095ea7b3": ("ERC20 approve", "approval"),
    "0x42842e0e": ("ERC721 safeTransferFrom", "nft_transfer"),
    "0xa22cb465": ("ERC721 setApprovalForAll", "approval"),
    "0x40c10f19": ("ERC20 mint", "mint"),
    "0x6a627842": ("ERC721 mint", "nft_mint"),
    "0xd0e30db0": ("WETH deposit", "wrap"),
    "0x2e1a7d4d": ("WETH withdraw", "unwrap"),
    "0xa0712d68": ("ERC721 mint(uint256)", "nft_mint"),
    "0x29ee566b": ("LayerZero send", "bridge"),
    "0xeb9d4d3d": ("AcrossV3 deposit", "bridge"),
    "0x96f4e9f9": ("Hop bridge", "bridge"),
}


def selector_hint(method_or_input: str) -> tuple[str, str] | None:
    """Recognize a function call by its 4-byte selector."""
    if not method_or_input:
        return None
    s = method_or_input.lower()
    if s.startswith("0x") and len(s) >= 10:
        sel = s[:10]
        return SELECTOR_HINTS.get(sel)
    return None


# ---------------------------------------------------------------------------
# Top-level resolver
# ---------------------------------------------------------------------------

async def resolve_contracts(
    chain_id: int,
    chain_slug: str,
    addresses: list[str],
    chain_data,
    api_key: str | None,
    cross_chain_lookup: dict[str, list] | None = None,
) -> dict[str, ContractIdentity]:
    """Resolve a batch of addresses on one chain.

    Returns: {addr_lc: ContractIdentity}. Always returns an entry per input
    even if resolution failed (with `name=None, source=fallback`) so callers
    can rely on key presence.

    `cross_chain_lookup` is an optional dict {chain_slug: ChainData} used to
    enrich token names from any chain where the wallet touched the token.
    """
    from .profiler import KNOWN_CONTRACTS

    out: dict[str, ContractIdentity] = {}
    addrs = [a.lower() for a in addresses if a]

    # Step 1: curated dict
    remaining: list[str] = []
    for a in addrs:
        if a in KNOWN_CONTRACTS:
            cat, label = KNOWN_CONTRACTS[a]
            out[a] = ContractIdentity(a, chain_slug, label, cat, "known")
        else:
            remaining.append(a)

    # Step 2: cache
    still: list[str] = []
    for a in remaining:
        cached = lookup_cache(chain_slug, a)
        if cached:
            out[a] = cached
        else:
            still.append(a)

    # Step 3+4: ERC20 / NFT name harvesting from THIS chain's data first,
    # then any other chain where the wallet touched the same token (some
    # bridges/proxies have the same contract address across chains).
    token_names = harvest_token_names(chain_data) if chain_data else {}
    if cross_chain_lookup:
        for slug, cd in cross_chain_lookup.items():
            if slug == chain_slug or cd is None:
                continue
            for addr, val in harvest_token_names(cd).items():
                if addr not in token_names:
                    token_names[addr] = val

    api_targets: list[str] = []
    for a in still:
        if a in token_names:
            name, cat = token_names[a]
            ident = ContractIdentity(a, chain_slug, name, cat, "token")
            out[a] = ident
            store_cache(chain_slug, a, name, cat, "token")
        else:
            api_targets.append(a)

    # Step 5: Etherscan getsourcecode (only if we have a key & sensible budget)
    if api_key and api_targets:
        async with httpx.AsyncClient() as client:
            tasks = [
                _fetch_etherscan_name(client, chain_id, a, api_key)
                for a in api_targets
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        for a, res in zip(api_targets, results):
            if isinstance(res, tuple):
                name, cat = res
                ident = ContractIdentity(a, chain_slug, name, cat, "etherscan")
                out[a] = ident
                store_cache(chain_slug, a, name, cat, "etherscan")
            else:
                # Etherscan returned nothing — store negative result briefly
                store_cache(chain_slug, a, None, "unknown", "etherscan_miss")
                out[a] = ContractIdentity(a, chain_slug, None, "unknown", "fallback")
    else:
        for a in api_targets:
            out[a] = ContractIdentity(a, chain_slug, None, "unknown", "fallback")

    return out


def short_address(addr: str, head: int = 8, tail: int = 6) -> str:
    """Return 0xabcd1234…ef5678-style display form."""
    if not addr or len(addr) < head + tail + 2:
        return addr or ""
    return f"{addr[:head + 2]}…{addr[-tail:]}"
