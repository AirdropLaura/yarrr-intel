"""Archetype scoring engine — Layer 2 brain.

Takes a raw `WalletDigest` (already populated with quantitative signals) and
runs a curated set of archetype detectors. Each detector returns a confidence
score (0.0–1.0) plus a one-line evidence string the analyst prompt can quote.

Detectors are intentionally simple, transparent, and chain-agnostic. They run
on the digest, not raw txs — that means the LLM sees the same evidence the
heuristic saw, and we can audit "why was this flagged airdrop_hunter?".

Confidence is bucketed for the prompt:
- 0.85+ → "strong"
- 0.6+  → "moderate"
- 0.35+ → "tentative"
- below → not surfaced

Adding a new archetype = adding one function + registering it in ARCHETYPES.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Archetype:
    name: str
    confidence: float       # 0.0–1.0
    evidence: list[str]     # short factual bullets
    bucket: str = "tentative"  # filled by `bucket_for`


def bucket_for(conf: float) -> str:
    if conf >= 0.85: return "strong"
    if conf >= 0.6:  return "moderate"
    if conf >= 0.35: return "tentative"
    return "weak"


# ---------------------------------------------------------------------------
# Inputs the detectors consume. All derived from the profiler digest.
# ---------------------------------------------------------------------------
@dataclass
class ArchetypeInputs:
    total_txs: int
    days_active: int
    days_since_last_tx: int | None
    error_rate: float
    chains_active: list[str]
    chains_dormant: list[str]
    testnet_chains_active: list[str]
    mainnet_chains_active: list[str]
    activity_categories: dict[str, int]   # initiated tx categories
    top_contracts: list[dict]             # [{address, hits, category, label, chains}]
    bridge_events: int
    nft_events: int
    swap_events: int
    approval_events: int
    mint_events: int
    governance_events: int
    stake_events: int
    total_balance_native: float           # sum of native balances across chains
    funding_hint: str | None              # "cex_deposit" | "bridge" | "airdrop_claim" | None
    wallet_age_days: int
    # Phase 2a token signals
    stablecoin_volume_usd: float = 0.0
    distinct_stablecoins: int = 0
    holds_lp_tokens: bool = False
    holds_lst_tokens: bool = False
    distinct_nft_collections: int = 0
    spam_nft_count: int = 0
    failed_tx_cluster_count: int = 0


# ---------------------------------------------------------------------------
# Detectors — each returns (confidence, evidence_lines).
# Confidence rules of thumb:
#   0.0–0.34 = not enough signal
#   0.35–0.59 = tentative match
#   0.6–0.84 = clear match
#   0.85–1.0 = textbook example
# ---------------------------------------------------------------------------

def detect_fresh_wallet(i: ArchetypeInputs) -> tuple[float, list[str]]:
    if i.total_txs == 0:
        return 0.0, []
    ev: list[str] = []
    score = 0.0
    if i.wallet_age_days <= 7:
        score += 0.6
        ev.append(f"wallet age ≤ {i.wallet_age_days}d (very young)")
    elif i.wallet_age_days <= 30:
        score += 0.35
        ev.append(f"wallet age {i.wallet_age_days}d (under a month)")
    if i.total_txs <= 20:
        score += 0.2
        ev.append(f"only {i.total_txs} sampled tx so far")
    return min(score, 1.0), ev


def detect_airdrop_hunter(i: ArchetypeInputs) -> tuple[float, list[str]]:
    ev: list[str] = []
    score = 0.0
    # Multi-chain footprint with low value flowing → classic farming pattern.
    if len(i.mainnet_chains_active) >= 4:
        score += 0.35
        ev.append(f"active on {len(i.mainnet_chains_active)} mainnets — broad ecosystem coverage")
    if i.bridge_events >= 3:
        score += 0.25
        ev.append(f"{i.bridge_events} bridge events — repeated cross-chain hopping")
    if i.swap_events >= 5 and i.total_balance_native < 0.5:
        score += 0.15
        ev.append("frequent swaps with low residual balance — capital cycled, not held")
    if "claim" in i.activity_categories:
        score += 0.2
        ev.append(f"{i.activity_categories['claim']} explicit claim() calls")
    return min(score, 1.0), ev


def detect_testnet_farmer(i: ArchetypeInputs) -> tuple[float, list[str]]:
    if not i.testnet_chains_active:
        return 0.0, []
    ev: list[str] = []
    score = 0.0
    n_test = len(i.testnet_chains_active)
    if n_test >= 3:
        score += 0.5
        ev.append(f"{n_test} active testnets ({', '.join(i.testnet_chains_active)})")
    elif n_test >= 1:
        score += 0.3
        ev.append(f"testnet activity on {', '.join(i.testnet_chains_active)}")
    # Testnet tx volume relative to mainnet.
    if i.testnet_chains_active and len(i.mainnet_chains_active) <= 1:
        score += 0.2
        ev.append("primarily testnet-resident — likely point/airdrop farming")
    return min(score, 1.0), ev


def detect_smart_money(i: ArchetypeInputs) -> tuple[float, list[str]]:
    ev: list[str] = []
    score = 0.0
    has_lending = any(c.get("category") == "lending" for c in i.top_contracts)
    has_dex = i.swap_events >= 5
    if has_lending:
        score += 0.3
        ev.append("uses lending protocols (Aave/Compound class)")
    if has_dex and i.swap_events >= 15:
        score += 0.25
        ev.append(f"{i.swap_events} swaps — sustained DEX usage")
    if i.governance_events >= 2:
        score += 0.2
        ev.append(f"{i.governance_events} governance votes")
    if i.stake_events >= 3:
        score += 0.15
        ev.append(f"{i.stake_events} stake/delegate events")
    if i.error_rate < 0.05 and i.total_txs >= 30:
        score += 0.1
        ev.append("low revert rate at scale — competent operator")
    # Phase 2a: holding LP / LST tokens raises confidence — these are active
    # DeFi positions, not bag-holding.
    if i.holds_lp_tokens:
        score += 0.15
        ev.append("holds LP tokens — active liquidity provider")
    if i.holds_lst_tokens:
        score += 0.1
        ev.append("holds LSTs (stETH/rETH/etc.) — yield-aware")
    return min(score, 1.0), ev


def detect_stablecoin_native(i: ArchetypeInputs) -> tuple[float, list[str]]:
    """Wallet whose balance / activity is mostly stablecoins.

    Strong signal: large stablecoin volume across multiple chains, multiple
    distinct stable tokens (USDC + USDT + DAI). Differs from smart_money
    because the wallet may not be doing yield — just parking capital.
    """
    if i.stablecoin_volume_usd < 1000:
        return 0.0, []
    ev: list[str] = []
    score = 0.0
    if i.stablecoin_volume_usd >= 100_000:
        score += 0.5
        ev.append(f"~${i.stablecoin_volume_usd:,.0f} stablecoin transfer volume sampled")
    elif i.stablecoin_volume_usd >= 10_000:
        score += 0.3
        ev.append(f"~${i.stablecoin_volume_usd:,.0f} stablecoin transfer volume sampled")
    else:
        score += 0.15
        ev.append(f"~${i.stablecoin_volume_usd:,.0f} stablecoin transfers sampled")
    if i.distinct_stablecoins >= 3:
        score += 0.15
        ev.append(f"{i.distinct_stablecoins} distinct stablecoins used")
    return min(score, 1.0), ev


def detect_spam_exposed(i: ArchetypeInputs) -> tuple[float, list[str]]:
    """Wallet has received spam NFTs / tokens. Doesn't mean the wallet is bad
    — just that it's old enough or visible enough to be targeted."""
    if i.spam_nft_count == 0:
        return 0.0, []
    score = min(0.4 + i.spam_nft_count * 0.05, 1.0)
    return score, [f"{i.spam_nft_count} suspected spam NFT drops received"]


def detect_high_revert_user(i: ArchetypeInputs) -> tuple[float, list[str]]:
    if i.total_txs < 10:
        return 0.0, []
    if i.error_rate < 0.15 and i.failed_tx_cluster_count == 0:
        return 0.0, []
    base = max(i.error_rate - 0.15, 0.0) * 2.0
    cluster_bonus = min(i.failed_tx_cluster_count * 0.08, 0.3)
    score = min(0.4 + base + cluster_bonus, 1.0)
    ev = [f"revert rate {i.error_rate*100:.0f}% across {i.total_txs} sampled tx"]
    if i.failed_tx_cluster_count >= 1:
        ev.append(f"{i.failed_tx_cluster_count} repeated-revert pattern(s) at the same target")
    return score, ev


def detect_nft_flipper(i: ArchetypeInputs) -> tuple[float, list[str]]:
    if i.nft_events == 0 and i.mint_events == 0:
        return 0.0, []
    ev: list[str] = []
    score = 0.0
    if i.nft_events >= 10:
        score += 0.4
        ev.append(f"{i.nft_events} NFT marketplace events")
    elif i.nft_events >= 4:
        score += 0.2
        ev.append(f"{i.nft_events} NFT marketplace events")
    if i.mint_events >= 5:
        score += 0.25
        ev.append(f"{i.mint_events} mint() calls")
    if i.nft_events and i.swap_events == 0:
        score += 0.15
        ev.append("NFT activity dominates — not a generic DeFi user")
    return min(score, 1.0), ev


def detect_dormant_whale(i: ArchetypeInputs) -> tuple[float, list[str]]:
    ev: list[str] = []
    score = 0.0
    if i.total_balance_native >= 5.0 and (i.days_since_last_tx or 0) >= 90:
        score += 0.7
        ev.append(f"{i.total_balance_native:.2f} native balance, dormant {i.days_since_last_tx}d")
    elif i.total_balance_native >= 1.0 and (i.days_since_last_tx or 0) >= 180:
        score += 0.4
        ev.append(f"{i.total_balance_native:.2f} native balance, dormant {i.days_since_last_tx}d")
    return min(score, 1.0), ev


def detect_long_term_holder(i: ArchetypeInputs) -> tuple[float, list[str]]:
    if i.wallet_age_days < 365:
        return 0.0, []
    ev: list[str] = []
    score = 0.0
    if i.wallet_age_days >= 365 * 2:
        score += 0.3
        ev.append(f"wallet age {i.wallet_age_days // 365}y+ — established")
    if i.total_txs / max(i.wallet_age_days, 1) < 0.05:
        score += 0.3
        ev.append("low tx velocity relative to age — passive holder pattern")
    if i.total_balance_native >= 0.5:
        score += 0.15
        ev.append(f"holds {i.total_balance_native:.2f} native")
    return min(score, 1.0), ev


def detect_high_revert_user_legacy(i: ArchetypeInputs) -> tuple[float, list[str]]:
    """Deprecated — replaced by the cluster-aware version above. Kept as a
    historical reference."""
    return 0.0, []


def detect_bridge_heavy(i: ArchetypeInputs) -> tuple[float, list[str]]:
    if i.bridge_events < 3:
        return 0.0, []
    score = min(0.3 + i.bridge_events * 0.06, 1.0)
    ev = [f"{i.bridge_events} bridge events, hopping {len(i.chains_active)} chains"]
    return score, ev


def detect_multi_chain_native(i: ArchetypeInputs) -> tuple[float, list[str]]:
    n = len(i.chains_active)
    if n < 4:
        return 0.0, []
    score = min(0.4 + (n - 4) * 0.1, 1.0)
    return score, [f"active on {n} chains simultaneously"]


def detect_burner_wallet(i: ArchetypeInputs) -> tuple[float, list[str]]:
    """Burner = small balance, narrow purpose, short lifespan, single chain."""
    if i.total_txs == 0 or i.total_txs > 30:
        return 0.0, []
    if len(i.chains_active) > 1:
        return 0.0, []
    if i.wallet_age_days > 14:
        return 0.0, []
    if i.total_balance_native > 0.1:
        return 0.0, []
    return 0.55, [
        f"single-chain ({i.chains_active[0] if i.chains_active else '?'}), "
        f"≤{i.total_txs} tx, ≤{i.wallet_age_days}d, near-zero balance"
    ]


def detect_sybil_candidate(i: ArchetypeInputs) -> tuple[float, list[str]]:
    """Cluster signals that match scripted farming.

    Real sybil detection requires graph analysis (Phase 3). This is a tentative
    pre-filter — wallet *patterns* that resemble a farming script:
    - Fresh wallet, narrow tx, multi-chain bridge cycles, claim() calls.
    """
    ev: list[str] = []
    score = 0.0
    if i.wallet_age_days <= 60 and i.bridge_events >= 2 and "claim" in i.activity_categories:
        score += 0.3
        ev.append("young + bridges + claims (script-like cadence)")
    if i.testnet_chains_active and len(i.testnet_chains_active) >= 3:
        score += 0.15
        ev.append("broad testnet farming surface")
    if i.error_rate >= 0.3 and i.total_txs >= 10:
        score += 0.1
        ev.append(f"high revert rate ({i.error_rate*100:.0f}%) suggests batch retry loops")
    return min(score, 1.0), ev


def detect_stablecoin_native_legacy(i: ArchetypeInputs) -> tuple[float, list[str]]:
    """Deprecated — replaced by the proper version above with ERC20 ingestion."""
    return 0.0, []


# Order matters only for stable rendering — not for logic. Strongest first looks
# better in the UI when many archetypes tie.
ARCHETYPES = [
    ("smart_money",        detect_smart_money),
    ("airdrop_hunter",     detect_airdrop_hunter),
    ("testnet_farmer",     detect_testnet_farmer),
    ("stablecoin_native",  detect_stablecoin_native),
    ("nft_flipper",        detect_nft_flipper),
    ("dormant_whale",      detect_dormant_whale),
    ("long_term_holder",   detect_long_term_holder),
    ("multi_chain_native", detect_multi_chain_native),
    ("bridge_heavy",       detect_bridge_heavy),
    ("fresh_wallet",       detect_fresh_wallet),
    ("burner_wallet",      detect_burner_wallet),
    ("high_revert_user",   detect_high_revert_user),
    ("spam_exposed",       detect_spam_exposed),
    ("sybil_candidate",    detect_sybil_candidate),
]


def score_archetypes(i: ArchetypeInputs) -> list[Archetype]:
    """Run all detectors. Return only those scoring tentative or higher."""
    out: list[Archetype] = []
    for name, fn in ARCHETYPES:
        conf, ev = fn(i)
        if conf < 0.35:
            continue
        out.append(Archetype(
            name=name,
            confidence=round(conf, 2),
            evidence=ev,
            bucket=bucket_for(conf),
        ))
    out.sort(key=lambda a: a.confidence, reverse=True)
    return out
