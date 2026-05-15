"""Wallet profiler — turn raw multichain tx history into a compact digest
suitable for LLM analysis.

Goal: reduce 250 raw transactions (verbose JSON) into ~600-1500 input tokens
that capture the meaningful behavioral signal:

- Activity timeline (oldest tx, latest tx, total tx, error rate)
- Per-chain distribution
- Top counterparty contracts (clustered by frequency, with classification)
- Notable categories (bridges, NFTs, swaps, mints, faucets, lending)
- Recent activity highlights (last 5-10 txs in plain English)

Heuristic classification uses a curated lookup table of well-known protocol
contracts. Anything unknown is preserved as `unknown` so the LLM can reason
about it from address + method name.
"""
from __future__ import annotations

import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .chain import ChainData

# ---------------------------------------------------------------------------
# Known protocol classification (curated, lowercase)
# ---------------------------------------------------------------------------
# Format: { lowercase_address: (category, label) }
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
    # Lending
    "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2":  ("lending", "Aave v3 Pool"),
    "0xa17581a9e3356d9a858b789d68b4d866e593ae94":  ("lending", "Compound USDC"),
    "0x5d3a536e4d6dbd6114cc1ead35777bab948e3643":  ("lending", "Compound DAI"),
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


def _classify_method(method: str) -> str | None:
    if not method:
        return None
    m = method.lower()
    for keywords, cat in METHOD_HINTS:
        if any(k.lower() in m for k in keywords):
            return cat
    return None


@dataclass
class WalletDigest:
    address: str
    chains_active: list[str] = field(default_factory=list)
    chains_dormant: list[str] = field(default_factory=list)
    total_balance_eth_equiv: float = 0.0
    balances_by_chain: dict[str, float] = field(default_factory=dict)
    total_txs: int = 0
    txs_by_chain: dict[str, int] = field(default_factory=dict)
    error_rate: float = 0.0
    first_tx_ts: int | None = None
    last_tx_ts: int | None = None
    days_active: int = 0
    days_since_last_tx: int | None = None
    activity_categories: dict[str, int] = field(default_factory=dict)
    top_contracts: list[dict] = field(default_factory=list)
    recent_actions: list[str] = field(default_factory=list)
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


def build_digest(address: str, all_chain_data: list[ChainData]) -> WalletDigest:
    addr_lower = address.lower()
    digest = WalletDigest(address=addr_lower)

    all_txs: list[dict] = []
    contract_hits: Counter[str] = Counter()
    contract_chain: dict[str, set[str]] = defaultdict(set)
    error_total = 0

    for cd in all_chain_data:
        digest.balances_by_chain[cd.chain] = round(cd.balance, 6)
        digest.txs_by_chain[cd.chain] = cd.tx_count
        if cd.tx_count > 0 or cd.balance > 0:
            digest.chains_active.append(cd.chain)
        else:
            digest.chains_dormant.append(cd.chain)
        digest.total_balance_eth_equiv += cd.balance
        digest.total_txs += cd.tx_count

        for tx in cd.txs:
            all_txs.append(tx)
            if tx.get("is_error"):
                error_total += 1
            # Counterparty: when wallet is sender (`from`), counterparty is `to`.
            # When wallet is receiver, counterparty is `from`. Either way, we
            # never count the wallet's own address as a counterparty.
            tx_from = (tx.get("from") or "").lower()
            tx_to = (tx.get("to") or "").lower()
            if tx_from == addr_lower:
                cp = tx_to
            elif tx_to == addr_lower:
                cp = tx_from
            else:
                cp = tx_to  # internal/contract event
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

    # Top contracts
    top = contract_hits.most_common(15)
    for addr, count in top:
        cat, label = KNOWN_CONTRACTS.get(addr, ("unknown", "Unknown contract"))
        digest.top_contracts.append({
            "address": addr,
            "hits": count,
            "category": cat,
            "label": label,
            "chains": sorted(contract_chain[addr]),
        })

    # Activity category histogram — only count txs the wallet INITIATED
    # (incoming txs reflect what others did, not the wallet's behavior)
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
                cat_counter["contract_call"] += 1
            else:
                cat_counter["contract_deploy"] += 1
    digest.activity_categories = dict(cat_counter.most_common())

    # Recent actions
    sorted_txs = sorted(all_txs, key=lambda t: t.get("ts") or 0, reverse=True)
    digest.recent_actions = [_format_recent(t, addr_lower) for t in sorted_txs[:10]]

    # Flags
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

    return digest


def digest_to_prompt_block(digest: WalletDigest) -> str:
    """Render the digest as a compact markdown block ready to send to the LLM."""
    lines: list[str] = []
    lines.append(f"WALLET: `{digest.address}`")
    lines.append("")
    lines.append("### Activity overview")
    lines.append(f"- total transactions seen (last 50/chain): {digest.total_txs}")
    lines.append(f"- error / revert rate: {digest.error_rate*100:.1f}%")
    if digest.first_tx_ts and digest.last_tx_ts:
        lines.append(f"- first observed tx: {time.strftime('%Y-%m-%d', time.gmtime(digest.first_tx_ts))}")
        lines.append(f"- latest tx: {time.strftime('%Y-%m-%d', time.gmtime(digest.last_tx_ts))} ({digest.days_since_last_tx}d ago)")
        lines.append(f"- active span (within sampled tx): ~{digest.days_active}d")
    lines.append(f"- chains active: {', '.join(digest.chains_active) or 'none'}")
    if digest.chains_dormant:
        lines.append(f"- chains dormant: {', '.join(digest.chains_dormant)}")
    lines.append("")
    lines.append("### Native balances")
    for chain, bal in digest.balances_by_chain.items():
        lines.append(f"- {chain}: {bal:.4f}")
    lines.append("")
    lines.append("### Activity categories")
    if digest.activity_categories:
        for cat, n in digest.activity_categories.items():
            lines.append(f"- {cat}: {n}")
    else:
        lines.append("- (no classifiable activity)")
    lines.append("")
    lines.append("### Top counterparty contracts")
    if digest.top_contracts:
        for c in digest.top_contracts[:10]:
            chains = ",".join(c["chains"])
            lines.append(f"- {c['label']} ({c['category']}) — {c['hits']} hits across [{chains}] · `{c['address'][:10]}…{c['address'][-4:]}`")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("### Recent actions")
    for action in digest.recent_actions:
        lines.append(f"- {action}")
    lines.append("")
    lines.append("### Behavioral flags (heuristic)")
    if digest.flags:
        for f in digest.flags:
            lines.append(f"- {f}")
    else:
        lines.append("- (none triggered)")
    return "\n".join(lines)
