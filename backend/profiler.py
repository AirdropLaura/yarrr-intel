"""Wallet profiler — Layer 2 of the Yarrr.Tech pipeline.

Turns raw multichain tx history (Layer 1 output) into a structured behavioral
intelligence digest. The digest is what the LLM analyst (Layer 3) reasons over
— never raw transactions.

Goal: compress hundreds of txs across 15+ chains into ~600-1500 prompt tokens
that capture meaningful signal:

- Quantitative: tx counts, error rate, gas profile, age, dormancy
- Distribution: per-chain mainnet/testnet split, chain hopping
- Behavioral: activity categories, top counterparties, recent actions
- Funding: heuristic source (CEX deposit / bridge inbound / claim)
- Archetypes: scored candidate identities (airdrop_hunter, smart_money, ...)
- Risk: revert rate, approval count, dormant→burst patterns

Heuristic classification uses a curated lookup of well-known protocol
contracts. Anything unknown is preserved as `unknown` so the LLM can reason
about it from address + method name.
"""
from __future__ import annotations

import logging
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field

log = logging.getLogger("yarrr-tech.profiler")

from .archetypes import Archetype, ArchetypeInputs, score_archetypes
from .chain import ChainData, NFTTransfer, TokenTransfer
from .reputation import ReputationScore, compute_reputation, reputation_to_prompt_lines
from .tokens import is_lp_token, is_lst_token, is_stablecoin, looks_like_spam_nft

# ---------------------------------------------------------------------------
# Known protocol classification (curated, lowercase address → (category, label))
# ---------------------------------------------------------------------------
KNOWN_CONTRACTS: dict[str, tuple[str, str]] = {
    # Bridges
    "0x3154cf16ccdb4c6d922629664174b904d80f2c35":  ("bridge", "Base Bridge"),
    "0x49048044d57e1c92a77f79988d21fa8faf74e97e":  ("bridge", "Base Bridge (alt)"),
    "0x99c9fc46f92e8a1c0dec1b1747d010903e884be1":  ("bridge", "Optimism Bridge"),
    "0x4200000000000000000000000000000000000010":  ("bridge", "L2 StandardBridge"),
    "0x4200000000000000000000000000000000000007":  ("bridge", "L2 CrossDomainMessenger"),
    "0xd9d74a29307cc6fc8bf424ee4217f1a587fbc8dc":  ("bridge", "Across Spoke (Base)"),
    "0x09aea4b2242abc8bb4bb78d537a67a245a7bec64":  ("bridge", "Across Spoke (Eth)"),
    "0xae0ee0a63a2ce6baeeffe56e7714fb4efe48d419":  ("bridge", "LayerZero Endpoint"),
    "0x66a71dcef29a0ffbdbe3c6a460a3b5bc225cd675":  ("bridge", "LayerZero Endpoint v1"),
    "0x1a44076050125825900e736c501f859c50fe728c":  ("bridge", "LayerZero Endpoint v2"),
    "0x3a23f943181408eac424116af7b7790c94cb97a5":  ("bridge", "Socket Gateway"),
    "0x3e19d726ed435afd3a42967551426b3a47c0f5b7":  ("bridge", "Stargate"),
    "0x80c67432656d59144ceff962e8faf8926599bcf8":  ("bridge", "Orbiter Finance"),
    # DEX routers
    "0xe592427a0aece92de3edee1f18e0157c05861564":  ("dex", "Uniswap V3 Router"),
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45":  ("dex", "Uniswap V3 Router 2"),
    "0x2626664c2603336e57b271c5c0b26f421741e481":  ("dex", "Uniswap V3 (Base)"),
    "0x66e2ee16ce014c52d2c2dcd9a8f0e6e2a4ce8a4f":  ("dex", "Uniswap Universal Router"),
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d":  ("dex", "Uniswap V2 Router"),
    "0x10ed43c718714eb63d5aa57b78b54704e256024e":  ("dex", "PancakeSwap Router"),
    "0xd1c33d0af58eb7403f7c01b21307713aa18b29d3":  ("dex", "1inch Router"),
    "0x1111111254eeb25477b68fb85ed929f73a960582":  ("dex", "1inch v5 Router"),
    "0x111111125421ca6dc452d289314280a0f8842a65":  ("dex", "1inch v6 Router"),
    "0xdef1c0ded9bec7f1a1670819833240f027b25eff":  ("dex", "0x Exchange Proxy"),
    "0x6131b5fae19ea4f9d964eac0408e4408b66337b5":  ("dex", "KyberSwap Aggregator"),
    # Lending
    "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2":  ("lending", "Aave v3 Pool"),
    "0xa17581a9e3356d9a858b789d68b4d866e593ae94":  ("lending", "Compound USDC"),
    "0x5d3a536e4d6dbd6114cc1ead35777bab948e3643":  ("lending", "Compound DAI"),
    "0xe592427a0aece92de3edee1f18e0157c05861564":  ("dex", "Uniswap V3 Router"),
    # NFT marketplaces
    "0x00000000000000adc04c56bf30ac9d3c0aaf14dc":  ("nft", "Seaport (OpenSea)"),
    "0x0000000000000068f116a894984e2db1123eb395":  ("nft", "Seaport 1.6"),
    "0x000000008924d42d98026c656545c3c1fb3ad31c":  ("nft", "Seaport 1.5"),
    "0x59728544b08ab483533076417fbbb2fd0b17ce3a":  ("nft", "LooksRare"),
    "0x0000000000000a39bb272e79075ade125fd351887":  ("nft", "Blur Marketplace"),
    "0x000000000000ad05ccc4f10045630fb830b95127":  ("nft", "Blur Bid"),
    "0x39da41747a83aee658334415666f3ef92dd0d541":  ("nft", "MagicEden"),
    # Permit2 / approvals
    "0x000000000022d473030f116ddee9f6b43ac78ba3":  ("approval", "Uniswap Permit2"),
    # Common misc
    "0x000000000000000000000000000000000000dead":  ("burn", "Burn"),
}

# Method-name keywords → category override / hint
METHOD_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("mint",),                                    "nft_mint"),
    (("claim",),                                   "claim"),
    (("bridge", "depositTo", "sendFrom"),          "bridge"),
    (("swap", "exactInput", "exactOutput"),        "swap"),
    (("approve",),                                 "approval"),
    (("transfer",),                                "transfer"),
    (("stake", "deposit"),                         "stake"),
    (("delegate",),                                "stake"),
    (("vote", "castVote"),                         "governance"),
]

# Known CEX deposit address fragments (matched by prefix on `from` field).
# Used for funding source heuristic. Lowercase. Add more as we observe them.
KNOWN_CEX_HOTWALLETS: dict[str, str] = {
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance 14",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance 15",
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": "Binance 16",
    "0xa910f92acdaf488fa6ef02174fb86208ad7722ba": "OKX",
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": "OKX 2",
    "0x46340b20830761efd32832a74d7169b29feb9758": "Crypto.com",
    "0x77696bb39917c91a0c3908d577d5e322095425ca": "Coinbase",
    "0x71660c4005ba85c37ccec55d0c4493e66fe775d3": "Coinbase 1",
    "0x503828976d22510aad0201ac7ec88293211d23da": "Coinbase 2",
    "0xddfabcdc4d8ffc6d5beaf154f18b778f892a0740": "Coinbase 3",
    "0x3cd751e6b0078be393132286c442345e5dc49699": "Coinbase 4",
    "0x6262998ced04146fa42253a5c0af90ca02dfd2a3": "Crypto.com 2",
    "0xd24400ae8bfebb18ca49be86258a3c749cf46853": "Gemini",
    "0xfdb16996831753d5331ff813c29a93c76834a0ad": "Bitfinex",
    "0x59a5208b32e627891c389ebafc644145224006e8": "HitBTC",
}


def _classify_method(method: str) -> str | None:
    if not method:
        return None
    m = method.lower()
    for keywords, cat in METHOD_HINTS:
        if any(k.lower() in m for k in keywords):
            return cat
    return None


@dataclass
class TokenSignals:
    """Aggregated ERC20 + NFT activity signals across all chains."""
    stablecoin_volume_usd: float = 0.0          # rough sum of stablecoin transfer amounts
    stablecoin_chains: list[str] = field(default_factory=list)
    distinct_stablecoins: list[str] = field(default_factory=list)
    distinct_erc20: int = 0                      # # of unique non-stablecoin ERC20s seen
    holds_lp_tokens: bool = False
    holds_lst_tokens: bool = False
    distinct_nft_collections: int = 0
    spam_nft_count: int = 0
    spam_nft_examples: list[str] = field(default_factory=list)


@dataclass
class TimelinePeriod:
    """A behavioral phase in the wallet's life — derived by bucketing tx timestamps.

    Buckets are uniform-width (count-based) so the visualization can show
    relative activity intensity. Width on screen ∝ duration in seconds,
    height/intensity ∝ tx count in the bucket.
    """
    start_ts: int
    end_ts: int
    tx_count: int
    chains: list[str]              # distinct chains active in this period
    dominant_category: str | None  # most common initiated category
    error_rate: float


@dataclass
class FailedTxCluster:
    """A failure pattern: ≥3 reverts to the same target on the same chain."""
    chain: str
    target: str          # counterparty address
    method: str | None
    count: int


@dataclass
class WalletDigest:
    address: str
    name: str | None = None        # ENS / Basename if resolved

    # Chain footprint
    chains_active: list[str] = field(default_factory=list)
    chains_dormant: list[str] = field(default_factory=list)
    mainnet_chains_active: list[str] = field(default_factory=list)
    testnet_chains_active: list[str] = field(default_factory=list)

    # Balances
    total_balance_native: float = 0.0   # sum across mainnets only
    balances_by_chain: dict[str, float] = field(default_factory=dict)

    # Tx volume
    total_txs: int = 0
    txs_by_chain: dict[str, int] = field(default_factory=dict)
    error_rate: float = 0.0

    # Time signals
    first_tx_ts: int | None = None
    last_tx_ts: int | None = None
    days_active: int = 0
    days_since_last_tx: int | None = None
    wallet_age_days: int = 0

    # Behavior
    activity_categories: dict[str, int] = field(default_factory=dict)
    top_contracts: list[dict] = field(default_factory=list)
    recent_actions: list[str] = field(default_factory=list)

    # Funding heuristic
    funding_source: str | None = None      # "cex_deposit" | "bridge" | "airdrop_claim" | None
    funding_evidence: list[str] = field(default_factory=list)

    # Token signals (Phase 2a)
    tokens: TokenSignals = field(default_factory=TokenSignals)

    # Failed tx pattern analysis (Phase 2a)
    failed_tx_clusters: list[FailedTxCluster] = field(default_factory=list)

    # Timeline (Phase 2c) — bucketed activity periods for visualization
    timeline: list[TimelinePeriod] = field(default_factory=list)

    # Archetypes — primary intelligence output
    archetypes: list[Archetype] = field(default_factory=list)

    # Composite reputation (Phase 3.3) — derived AFTER archetypes are scored.
    reputation: ReputationScore | None = None

    # Heuristic flags (legacy, kept for backwards compat with frontend)
    flags: list[str] = field(default_factory=list)


def _format_recent(tx: dict, wallet_addr: str) -> str:
    ts = tx.get("ts") or 0
    when = "unknown" if not ts else _human_age(int(time.time()) - ts)
    chain = tx.get("chain", "?")
    method = tx.get("method") or "(transfer)"
    tx_from = (tx.get("from") or "").lower()
    tx_to = (tx.get("to") or "").lower()
    direction = "→" if tx_from == wallet_addr else "←"
    counterparty = tx_to if tx_from == wallet_addr else tx_from
    cat_lbl = ""
    if counterparty in KNOWN_CONTRACTS:
        category, label = KNOWN_CONTRACTS[counterparty]
        cat_lbl = f" {label}"
    elif counterparty in KNOWN_CEX_HOTWALLETS:
        cat_lbl = f" {KNOWN_CEX_HOTWALLETS[counterparty]} (CEX)"
    elif counterparty:
        cat_lbl = f" {counterparty[:8]}…{counterparty[-4:]}"
    err_marker = "  [REVERTED]" if tx.get("is_error") else ""
    return f"{when} on {chain}: {direction} {method}{cat_lbl}{err_marker}"


def _human_age(secs: int) -> str:
    if secs < 60: return f"{secs}s ago"
    if secs < 3600: return f"{secs // 60}m ago"
    if secs < 86400: return f"{secs // 3600}h ago"
    if secs < 30 * 86400: return f"{secs // 86400}d ago"
    if secs < 365 * 86400: return f"{secs // (30 * 86400)}mo ago"
    return f"{secs // (365 * 86400)}y ago"


def _infer_funding_source(all_txs: list[dict], wallet: str) -> tuple[str | None, list[str], dict | None]:
    """Pick the earliest *inbound* tx that explains how the wallet got funded.

    Order of preference: CEX hotwallet > bridge contract > airdrop claim.
    Returns (source_tag, evidence_lines, raw_event). The raw_event dict is
    used by the cluster module to index funding for sybil graph queries —
    it contains: source_addr, chain, ts, tx_hash, value_eth.
    """
    inbound = [t for t in all_txs if (t.get("to") or "").lower() == wallet
               and (t.get("from") or "").lower() != wallet
               and not t.get("is_error")
               and (t.get("value_eth") or 0) > 0]
    inbound.sort(key=lambda t: t.get("ts") or 0)
    for t in inbound[:5]:
        sender = (t.get("from") or "").lower()
        chain = t.get("chain", "?")
        ts = t.get("ts") or 0
        date = time.strftime("%Y-%m-%d", time.gmtime(ts)) if ts else "unknown"
        raw = {
            "source_addr": sender,
            "chain": chain,
            "ts": ts,
            "tx_hash": t.get("hash"),
            "value_eth": float(t.get("value_eth") or 0),
        }
        if sender in KNOWN_CEX_HOTWALLETS:
            label = KNOWN_CEX_HOTWALLETS[sender]
            raw["source_type"] = "cex"
            return "cex_deposit", [f"first inbound from {label} on {chain} at {date}"], raw
        if sender in KNOWN_CONTRACTS and KNOWN_CONTRACTS[sender][0] == "bridge":
            label = KNOWN_CONTRACTS[sender][1]
            raw["source_type"] = "bridge"
            return "bridge", [f"first inbound from {label} on {chain} at {date}"], raw
    # Outbound claim()?
    for t in all_txs:
        if (t.get("from") or "").lower() != wallet:
            continue
        method = (t.get("method") or "").lower()
        if "claim" in method:
            return "airdrop_claim", [f"earliest claim() to {t.get('to', '?')[:10]}… on {t.get('chain', '?')}"], None
    return None, [], None


def _analyze_tokens(all_chain_data: list[ChainData], wallet: str) -> TokenSignals:
    """Aggregate ERC20 + NFT signals across primary mainnets.

    Stablecoin volume is approximated by summing transfer amounts (in token
    units, treating 1 stablecoin ≈ 1 USD). Good enough for "this wallet moved
    tens of thousands of dollars in stablecoins" inference. Not exact.
    """
    sigs = TokenSignals()
    sc_volume = 0.0
    sc_chains: set[str] = set()
    sc_symbols: set[str] = set()
    erc20_contracts: set[str] = set()
    lp_seen = False
    lst_seen = False

    nft_collections: set[str] = set()
    spam_nfts: list[str] = []

    for cd in all_chain_data:
        if cd.is_testnet:
            continue
        for tx in cd.erc20_transfers:
            sym = is_stablecoin(tx.contract)
            if sym:
                sc_volume += tx.amount
                sc_chains.add(cd.chain)
                sc_symbols.add(sym)
            else:
                erc20_contracts.add(tx.contract)
                if is_lp_token(tx.symbol):
                    lp_seen = True
                if is_lst_token(tx.symbol):
                    lst_seen = True

        for nft in cd.nft_transfers:
            nft_collections.add(f"{cd.chain}:{nft.contract}")
            if looks_like_spam_nft(nft.name, nft.symbol):
                if (nft.to_addr or "").lower() == wallet:
                    label = nft.name or nft.symbol or nft.contract[:12]
                    spam_nfts.append(label)

    sigs.stablecoin_volume_usd = round(sc_volume, 2)
    sigs.stablecoin_chains = sorted(sc_chains)
    sigs.distinct_stablecoins = sorted(sc_symbols)
    sigs.distinct_erc20 = len(erc20_contracts)
    sigs.holds_lp_tokens = lp_seen
    sigs.holds_lst_tokens = lst_seen
    sigs.distinct_nft_collections = len(nft_collections)
    sigs.spam_nft_count = len(spam_nfts)
    # Trim to 5 examples — enough for evidence, doesn't blow up the prompt.
    sigs.spam_nft_examples = list({s for s in spam_nfts})[:5]
    return sigs


def _failed_tx_clusters(all_txs: list[dict], wallet: str) -> list[FailedTxCluster]:
    """Group reverted txs initiated by the wallet by (chain, target, method).

    Surface only clusters of 3+ — single reverts are noise, but repeated
    reverts to the same contract are meaningful (failed mints, slippage,
    permit timing, etc.). The analyst can interpret.
    """
    buckets: dict[tuple[str, str, str], int] = {}
    for tx in all_txs:
        if not tx.get("is_error"):
            continue
        if (tx.get("from") or "").lower() != wallet:
            continue
        chain = tx.get("chain", "?")
        target = (tx.get("to") or "").lower() or "(none)"
        method = (tx.get("method") or "").lower() or "(transfer)"
        key = (chain, target, method)
        buckets[key] = buckets.get(key, 0) + 1

    out: list[FailedTxCluster] = []
    for (chain, target, method), n in sorted(buckets.items(), key=lambda kv: -kv[1]):
        if n >= 3:
            out.append(FailedTxCluster(
                chain=chain,
                target=target,
                method=method if method != "(transfer)" else None,
                count=n,
            ))
        if len(out) >= 5:
            break
    return out


def _build_timeline(all_txs: list[dict], wallet: str, max_buckets: int = 10) -> list[TimelinePeriod]:
    """Bucket the wallet's tx history into time-based periods for visualization.

    Strategy:
    - Sort all txs by timestamp ascending.
    - Split into N equal-time buckets between first and last tx.
    - For each bucket compute: tx_count, distinct chains, dominant category,
      error rate.

    Equal-time buckets (vs equal-count) are right for showing dormancy: if a
    wallet was active in 2024 then dormant for 6 months then re-engaged, the
    timeline shows the dormant gap as low-intensity buckets.
    """
    txs = [t for t in all_txs if t.get("ts")]
    if len(txs) < 3:
        return []

    txs.sort(key=lambda t: t["ts"])
    t_first = txs[0]["ts"]
    t_last = txs[-1]["ts"]
    if t_last <= t_first:
        return []

    span = t_last - t_first
    n = min(max_buckets, max(3, len(txs) // 5))
    bucket_size = max(span / n, 1)

    buckets: list[list[dict]] = [[] for _ in range(n)]
    for t in txs:
        idx = min(int((t["ts"] - t_first) / bucket_size), n - 1)
        buckets[idx].append(t)

    out: list[TimelinePeriod] = []
    for i, bucket in enumerate(buckets):
        if not bucket:
            # Skip empty buckets entirely — caller can render a gap from the
            # boundary timestamps if desired.
            continue
        b_start = int(t_first + i * bucket_size)
        b_end = int(t_first + (i + 1) * bucket_size)
        chains = sorted({(t.get("chain") or "?") for t in bucket})
        cat_counts: Counter[str] = Counter()
        errors = 0
        for t in bucket:
            if t.get("is_error"):
                errors += 1
            if (t.get("from") or "").lower() != wallet:
                continue
            to = (t.get("to") or "").lower()
            if to in KNOWN_CONTRACTS:
                cat_counts[KNOWN_CONTRACTS[to][0]] += 1
            else:
                mc = _classify_method(t.get("method", ""))
                if mc:
                    cat_counts[mc] += 1
        dominant = cat_counts.most_common(1)[0][0] if cat_counts else None
        out.append(TimelinePeriod(
            start_ts=b_start,
            end_ts=b_end,
            tx_count=len(bucket),
            chains=chains,
            dominant_category=dominant,
            error_rate=round(errors / len(bucket), 3) if bucket else 0.0,
        ))
    return out


def build_digest(address: str, all_chain_data: list[ChainData], name: str | None = None) -> WalletDigest:
    addr_lower = address.lower()
    digest = WalletDigest(address=addr_lower, name=name)

    all_txs: list[dict] = []
    contract_hits: Counter[str] = Counter()
    contract_chain: dict[str, set[str]] = defaultdict(set)
    error_total = 0

    for cd in all_chain_data:
        digest.balances_by_chain[cd.chain] = round(cd.balance, 6)
        digest.txs_by_chain[cd.chain] = cd.tx_count
        if cd.tx_count > 0 or cd.balance > 0:
            digest.chains_active.append(cd.chain)
            if cd.is_testnet:
                digest.testnet_chains_active.append(cd.chain)
            else:
                digest.mainnet_chains_active.append(cd.chain)
        else:
            digest.chains_dormant.append(cd.chain)
        if not cd.is_testnet:
            digest.total_balance_native += cd.balance
        digest.total_txs += cd.tx_count

        for tx in cd.txs:
            all_txs.append(tx)
            if tx.get("is_error"):
                error_total += 1
            tx_from = (tx.get("from") or "").lower()
            tx_to = (tx.get("to") or "").lower()
            if tx_from == addr_lower:
                cp = tx_to
            elif tx_to == addr_lower:
                cp = tx_from
            else:
                cp = tx_to
            if cp and cp != addr_lower and cp != "0x0000000000000000000000000000000000000000":
                contract_hits[cp] += 1
                contract_chain[cp].add(cd.chain)

    if digest.total_txs:
        digest.error_rate = round(error_total / digest.total_txs, 3)

    # Time signals
    timestamps = [t.get("ts") for t in all_txs if t.get("ts")]
    if timestamps:
        digest.first_tx_ts = min(timestamps)
        digest.last_tx_ts = max(timestamps)
        span = digest.last_tx_ts - digest.first_tx_ts
        digest.days_active = max(span // 86400, 1)
        digest.days_since_last_tx = max(int(time.time()) - digest.last_tx_ts, 0) // 86400
        digest.wallet_age_days = max((int(time.time()) - digest.first_tx_ts) // 86400, 1)

    # Top contracts — placeholder now, resolved later via enrich_top_contracts()
    # The first pass tags only known contracts; remaining ones get resolved
    # asynchronously after build_digest returns. This keeps build_digest pure
    # while letting us enrich names from token transfers + Etherscan API.
    top = contract_hits.most_common(15)
    for addr, count in top:
        cat, label = KNOWN_CONTRACTS.get(addr, ("unknown", "Unknown contract"))
        # Mark which chain(s) this contract was seen on so the resolver knows
        # where to look up the verified name.
        chains = sorted(contract_chain[addr])
        digest.top_contracts.append({
            "address": addr,
            "hits": count,
            "category": cat,
            "label": label,
            "chains": chains,
        })

    # Activity category histogram — only count txs the wallet INITIATED.
    cat_counter: Counter[str] = Counter()
    for tx in all_txs:
        tx_from = (tx.get("from") or "").lower()
        if tx_from != addr_lower:
            continue  # incoming, skip for behavior categorization
        to = (tx.get("to") or "").lower()
        if to in KNOWN_CONTRACTS:
            cat_counter[KNOWN_CONTRACTS[to][0]] += 1
        else:
            mc = _classify_method(tx.get("method", ""))
            if mc:
                cat_counter[mc] += 1
            elif to:
                cat_counter[ "contract_call"] += 1
            else:
                cat_counter["contract_deploy"] += 1
    digest.activity_categories = dict(cat_counter.most_common())

    # Recent actions
    sorted_txs = sorted(all_txs, key=lambda t: t.get("ts") or 0, reverse=True)
    digest.recent_actions = [_format_recent(t, addr_lower) for t in sorted_txs[:10]]

    # Funding source heuristic
    src, ev, raw_funding = _infer_funding_source(all_txs, addr_lower)
    digest.funding_source = src
    digest.funding_evidence = ev

    # Index the funding event for sybil graph clustering (Phase 3.4).
    # We only record events with a high-signal source type — CEX hot wallets
    # and bridge contracts — to keep the index targeted.
    if raw_funding and raw_funding.get("source_type") in ("cex", "bridge"):
        try:
            from .cluster import FundingEvent, record_funding_event
            record_funding_event(FundingEvent(
                wallet=addr_lower,
                source_addr=raw_funding["source_addr"],
                source_type=raw_funding["source_type"],
                chain=raw_funding["chain"],
                ts=raw_funding["ts"],
                tx_hash=raw_funding.get("tx_hash"),
                value_eth=raw_funding.get("value_eth", 0.0),
            ))
        except Exception as e:
            # Never let indexing block analysis.
            log.debug("funding event indexing failed: %s", e)

    # Token signals (Phase 2a) — ERC20 + NFT aggregates from primary mainnets.
    digest.tokens = _analyze_tokens(all_chain_data, addr_lower)

    # Failed tx clusters — repeated reverts to the same target are meaningful
    # (failed mints, slippage on illiquid pools, permit2 timing issues).
    digest.failed_tx_clusters = _failed_tx_clusters(all_txs, addr_lower)

    # Timeline — bucketed activity periods for the analyst + frontend.
    digest.timeline = _build_timeline(all_txs, addr_lower)

    # ----- Archetype scoring -------------------------------------------------
    inputs = ArchetypeInputs(
        total_txs=digest.total_txs,
        days_active=digest.days_active,
        days_since_last_tx=digest.days_since_last_tx,
        error_rate=digest.error_rate,
        chains_active=digest.chains_active,
        chains_dormant=digest.chains_dormant,
        testnet_chains_active=digest.testnet_chains_active,
        mainnet_chains_active=digest.mainnet_chains_active,
        activity_categories=digest.activity_categories,
        top_contracts=digest.top_contracts,
        bridge_events=cat_counter.get("bridge", 0),
        nft_events=cat_counter.get("nft", 0),
        swap_events=cat_counter.get("swap", 0) + cat_counter.get("dex", 0),
        approval_events=cat_counter.get("approval", 0),
        mint_events=cat_counter.get("nft_mint", 0),
        governance_events=cat_counter.get("governance", 0),
        stake_events=cat_counter.get("stake", 0),
        total_balance_native=digest.total_balance_native,
        funding_hint=digest.funding_source,
        wallet_age_days=digest.wallet_age_days,
        stablecoin_volume_usd=digest.tokens.stablecoin_volume_usd,
        distinct_stablecoins=len(digest.tokens.distinct_stablecoins),
        holds_lp_tokens=digest.tokens.holds_lp_tokens,
        holds_lst_tokens=digest.tokens.holds_lst_tokens,
        distinct_nft_collections=digest.tokens.distinct_nft_collections,
        spam_nft_count=digest.tokens.spam_nft_count,
        failed_tx_cluster_count=len(digest.failed_tx_clusters),
    )
    digest.archetypes = score_archetypes(inputs)

    # ----- Composite reputation score (Phase 3.3) ----------------------------
    # Computed AFTER archetypes since it depends on them.
    digest.reputation = compute_reputation(digest)

    # ----- Legacy flags (compat with existing frontend) ----------------------
    if digest.total_txs == 0:
        digest.flags.append("no_activity")
    if digest.error_rate > 0.15:
        digest.flags.append(f"high_error_rate({digest.error_rate*100:.0f}%)")
    bridge_hits = cat_counter.get("bridge", 0)
    if bridge_hits >= 3:
        digest.flags.append(f"bridge_user({bridge_hits}_events)")
    nft_hits = cat_counter.get("nft", 0) + cat_counter.get("nft_mint", 0)
    if nft_hits >= 5:
        digest.flags.append(f"nft_active({nft_hits}_events)")
    if cat_counter.get("approval", 0) >= 3:
        digest.flags.append("multiple_approvals")
    if digest.days_since_last_tx is not None and digest.days_since_last_tx > 90:
        digest.flags.append(f"dormant({digest.days_since_last_tx}d)")
    if len(digest.chains_active) >= 4:
        digest.flags.append("multi_chain")
    if digest.testnet_chains_active:
        digest.flags.append(f"testnet_active({len(digest.testnet_chains_active)})")

    return digest


async def enrich_top_contracts(
    digest: WalletDigest,
    all_chain_data: list[ChainData],
) -> None:
    """Resolve missing names for top_contracts using contract_names module.

    Mutates digest.top_contracts in place. Safe to call after build_digest.
    Failures are silent — top_contracts retains its "Unknown contract" labels
    if any source returned nothing.
    """
    try:
        from .chain import _load_etherscan_key, get_chain
        from .contract_names import resolve_contracts

        api_key = _load_etherscan_key()

        # Group unresolved contracts by chain so each resolve_contracts call
        # is per-chain (Etherscan V2 lookup needs chain_id).
        per_chain: dict[str, list[str]] = {}
        for tc in digest.top_contracts:
            if tc.get("category") != "unknown":
                continue   # already known via curated dict
            for chain_slug in tc.get("chains") or []:
                per_chain.setdefault(chain_slug, []).append(tc["address"])

        if not per_chain:
            return

        # Build chain_data lookup so we can pass token transfers to the resolver
        cd_by_slug = {cd.chain: cd for cd in all_chain_data}

        # Resolve all chains in parallel (different chains are independent).
        # Pass full cd_by_slug as cross_chain_lookup so token name harvested on
        # one chain is reusable for the same address on another (LayerZero,
        # Stargate, Permit2 etc share addresses across chains).
        async def resolve_one(chain_slug: str, addrs: list[str]):
            chain = get_chain(chain_slug)
            if not chain:
                return chain_slug, {}
            cd = cd_by_slug.get(chain_slug)
            try:
                resolved = await resolve_contracts(
                    chain_id=chain.chain_id,
                    chain_slug=chain_slug,
                    addresses=addrs,
                    chain_data=cd,
                    api_key=api_key,
                    cross_chain_lookup=cd_by_slug,
                )
            except Exception as e:
                log.debug("resolve_contracts failed for %s: %s", chain_slug, e)
                return chain_slug, {}
            return chain_slug, resolved

        import asyncio
        results = await asyncio.gather(*[
            resolve_one(slug, addrs) for slug, addrs in per_chain.items()
        ])
        # Flatten — first resolution wins per address (chains are roughly
        # ordered primary→tertiary already; we trust the first hit).
        all_resolved: dict[str, "ContractIdentity"] = {}
        for _slug, m in results:
            for addr, ident in m.items():
                if addr not in all_resolved or all_resolved[addr].is_unknown():
                    all_resolved[addr] = ident

        # Fill back into digest.top_contracts (step 5/6 results)
        for tc in digest.top_contracts:
            ident = all_resolved.get(tc["address"])
            if ident and not ident.is_unknown():
                tc["category"] = ident.category
                tc["label"] = ident.name
                tc["resolution_source"] = ident.source

        # Step 7: Method-selector heuristic on remaining unknowns.
        # Look at the wallet's actual transactions to this contract — if it
        # consistently called the same selector, we can label it without
        # needing a verified ContractName. This catches unverified routers,
        # custom proxies, and forks of well-known contracts.
        # Also: if the wallet sent ETH directly with empty calldata to an
        # address (method == "0x" or ""), it's a peer-to-peer transfer, not a
        # contract interaction — label accordingly.
        unresolved_after_api = [
            tc["address"] for tc in digest.top_contracts
            if tc.get("category") == "unknown"
        ]
        if unresolved_after_api:
            from collections import Counter as _Counter
            from .contract_names import selector_hint, short_address, store_cache
            # Build per-contract selector frequency from raw txs across all chains
            sel_freq: dict[str, _Counter] = {}
            empty_method_count: dict[str, int] = {}
            total_count: dict[str, int] = {}
            for cd in all_chain_data:
                for tx in (cd.txs or []):
                    to = (tx.get("to") or "").lower()
                    if to in unresolved_after_api:
                        method = (tx.get("method") or "").lower().strip()
                        total_count[to] = total_count.get(to, 0) + 1
                        if method == "0x" or method == "":
                            empty_method_count[to] = empty_method_count.get(to, 0) + 1
                        elif method.startswith("0x") and len(method) >= 10:
                            sel = method[:10]
                            sel_freq.setdefault(to, _Counter())[sel] += 1

            for addr in unresolved_after_api:
                # Selector match wins
                hint = None
                if addr in sel_freq and sel_freq[addr]:
                    top_sel, _ = sel_freq[addr].most_common(1)[0]
                    hint = selector_hint(top_sel)

                if hint:
                    name, cat = hint
                    src = "selector"
                elif total_count.get(addr, 0) > 0 and empty_method_count.get(addr, 0) == total_count.get(addr, 0):
                    # All txs to this address were plain ETH transfers
                    name = "External wallet"
                    cat = "transfer"
                    src = "pattern"
                else:
                    # Final fallback: short address as label so the UI doesn't
                    # show a useless "Unknown contract" — at least the user can
                    # see WHICH contract it was.
                    chains = next(
                        (tc.get("chains") or [] for tc in digest.top_contracts if tc["address"] == addr),
                        [],
                    )
                    chain_label = chains[0] if chains else "?"
                    name = f"Contract on {chain_label}"
                    cat = "contract"
                    src = "fallback_short"

                for tc in digest.top_contracts:
                    if tc["address"] == addr:
                        tc["category"] = cat
                        tc["label"] = name
                        tc["resolution_source"] = src
                # Cache only verified-ish hits, not pattern fallbacks
                if src == "selector":
                    chains = next(
                        (tc.get("chains") or [] for tc in digest.top_contracts if tc["address"] == addr),
                        [],
                    )
                    if chains:
                        store_cache(chains[0], addr, name, cat, src)
    except Exception as e:
        log.debug("enrich_top_contracts failed: %s", e)


def digest_to_prompt_block(digest: WalletDigest) -> str:
    """Render the digest as a compact markdown block ready to send to the LLM.

    The shape here is deliberately consistent: stable headings, minimal noise,
    facts only. The analyst prompt is tuned against this exact structure.
    """
    lines: list[str] = []
    name_line = f" ({digest.name})" if digest.name else ""
    lines.append(f"WALLET: `{digest.address}`{name_line}")
    lines.append("")

    # Activity overview
    lines.append("### Activity overview")
    lines.append(f"- total transactions sampled: {digest.total_txs}")
    lines.append(f"- error / revert rate: {digest.error_rate*100:.1f}%")
    if digest.first_tx_ts and digest.last_tx_ts:
        lines.append(f"- first observed tx: {time.strftime('%Y-%m-%d', time.gmtime(digest.first_tx_ts))}")
        lines.append(f"- latest tx: {time.strftime('%Y-%m-%d', time.gmtime(digest.last_tx_ts))} ({digest.days_since_last_tx}d ago)")
        lines.append(f"- wallet age: ~{digest.wallet_age_days}d (active span ~{digest.days_active}d within sample)")
    lines.append(f"- mainnets active ({len(digest.mainnet_chains_active)}): {', '.join(digest.mainnet_chains_active) or 'none'}")
    lines.append(f"- testnets active ({len(digest.testnet_chains_active)}): {', '.join(digest.testnet_chains_active) or 'none'}")
    if digest.chains_dormant:
        # Keep this list short — LLM doesn't need to see 12 dormant chains.
        dormant = digest.chains_dormant[:8]
        suffix = f" (+{len(digest.chains_dormant) - len(dormant)} more)" if len(digest.chains_dormant) > len(dormant) else ""
        lines.append(f"- chains dormant/empty: {', '.join(dormant)}{suffix}")
    lines.append("")

    # Funding source — high-signal lead for the analyst
    if digest.funding_source:
        lines.append("### Funding source (heuristic)")
        lines.append(f"- inferred origin: {digest.funding_source}")
        for e in digest.funding_evidence:
            lines.append(f"  · {e}")
        lines.append("")

    # Native balances (mainnets only — testnet ETH is meaningless)
    lines.append("### Native balances (mainnets)")
    has_balance = False
    for chain, bal in digest.balances_by_chain.items():
        if bal > 0 and chain in digest.mainnet_chains_active:
            lines.append(f"- {chain}: {bal:.4f}")
            has_balance = True
    if not has_balance:
        lines.append("- (zero / dust on all sampled mainnets)")
    lines.append("")

    # Activity categories
    lines.append("### Activity categories (initiated by wallet)")
    if digest.activity_categories:
        for cat, n in digest.activity_categories.items():
            lines.append(f"- {cat}: {n}")
    else:
        lines.append("- (no classifiable initiated activity)")
    lines.append("")

    # Top counterparties
    lines.append("### Top counterparty contracts")
    if digest.top_contracts:
        for c in digest.top_contracts[:10]:
            chains = ",".join(c["chains"])
            lines.append(f"- {c['label']} ({c['category']}) — {c['hits']} hits across [{chains}] · `{c['address'][:10]}…{c['address'][-4:]}`")
    else:
        lines.append("- (none)")
    lines.append("")

    # Token signals (Phase 2a) — only render if there's anything worth saying
    if digest.tokens.distinct_erc20 or digest.tokens.stablecoin_volume_usd or digest.tokens.distinct_nft_collections:
        lines.append("### Token activity (primary mainnets)")
        if digest.tokens.stablecoin_volume_usd > 0:
            stables = ", ".join(digest.tokens.distinct_stablecoins) or "stablecoins"
            chains = ", ".join(digest.tokens.stablecoin_chains)
            lines.append(f"- stablecoin transfers sampled: ~${digest.tokens.stablecoin_volume_usd:,.0f} ({stables}) on [{chains}]")
        if digest.tokens.distinct_erc20:
            lines.append(f"- distinct non-stable ERC20 contracts touched: {digest.tokens.distinct_erc20}")
        if digest.tokens.holds_lp_tokens:
            lines.append("- holds / has held LP receipt tokens (Uniswap V2/V3, etc.)")
        if digest.tokens.holds_lst_tokens:
            lines.append("- holds / has held liquid staking tokens (stETH/rETH/cbETH/etc.)")
        if digest.tokens.distinct_nft_collections:
            lines.append(f"- distinct NFT collections seen: {digest.tokens.distinct_nft_collections}")
        if digest.tokens.spam_nft_count:
            examples = ", ".join(f'"{x}"' for x in digest.tokens.spam_nft_examples[:3])
            lines.append(f"- spam NFT drops received: {digest.tokens.spam_nft_count} ({examples})")
        lines.append("")

    # Failed tx clusters (Phase 2a)
    if digest.failed_tx_clusters:
        lines.append("### Repeated revert patterns")
        for fc in digest.failed_tx_clusters:
            method_part = f" via `{fc.method}`" if fc.method else ""
            short_target = f"{fc.target[:10]}…{fc.target[-4:]}" if len(fc.target) > 14 else fc.target
            lines.append(f"- {fc.count}× revert on {fc.chain}{method_part} → `{short_target}`")
        lines.append("")

    # Archetypes — the headline behavioral output
    lines.append("### Heuristic archetype candidates (with confidence)")
    if digest.archetypes:
        for a in digest.archetypes:
            lines.append(f"- **{a.name}** · {a.bucket} ({a.confidence:.2f})")
            for ev in a.evidence:
                lines.append(f"  · {ev}")
    else:
        lines.append("- (no archetype signal strong enough)")
    lines.append("")

    # Recent actions
    lines.append("### Recent actions")
    for action in digest.recent_actions:
        lines.append(f"- {action}")
    lines.append("")

    # Timeline (Phase 2c) — gives the analyst structured phase data so it can
    # describe evolution without making numbers up. We render compactly: each
    # bucket as a single line so the model sees the trend at a glance.
    if digest.timeline:
        lines.append("### Activity timeline (chronological buckets)")
        for tp in digest.timeline:
            start = time.strftime("%Y-%m-%d", time.gmtime(tp.start_ts))
            end = time.strftime("%Y-%m-%d", time.gmtime(tp.end_ts))
            chain_part = ",".join(tp.chains[:4])
            if len(tp.chains) > 4:
                chain_part += f"+{len(tp.chains) - 4}"
            cat_part = f" · {tp.dominant_category}" if tp.dominant_category else ""
            err_part = f" · err {tp.error_rate*100:.0f}%" if tp.error_rate >= 0.1 else ""
            lines.append(f"- {start} → {end}: {tp.tx_count} tx on [{chain_part}]{cat_part}{err_part}")
        lines.append("")

    # Reputation score (Phase 3.3) — surfaced to the analyst with full
    # transparency. The model can reference the number AND the contributions.
    if digest.reputation:
        lines.extend(reputation_to_prompt_lines(digest.reputation))

    # Legacy flag list
    lines.append("### Misc heuristic flags")
    if digest.flags:
        for f in digest.flags:
            lines.append(f"- {f}")
    else:
        lines.append("- (none triggered)")
    return "\n".join(lines)
