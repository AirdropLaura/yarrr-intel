"""Composite reputation score — Layer 2.5 of the Yarrr.Tech pipeline.

Takes a fully-populated `WalletDigest` and produces a single 0-100 score with
a transparent breakdown. The score is opinionated but explainable: each
contribution is named and weighted, so the frontend (and the LLM analyst) can
show *why* a wallet got the score it did.

Design notes:
- Score is NOT a credit score and NOT a "good wallet" judgment. It's a
  **shareability** index: would a serious onchain analyst be excited to find
  this wallet? Smart money / long-term holders score high because they're
  interesting to study. Sybil/spam-only wallets score low because they're
  noise.
- Contributions are bounded: any single signal can only move the score by its
  weight, so a wallet can't get to 100 just by being old. Multiple positive
  signals must compound.
- Negative signals (sybil candidate, high reverts, spam exposure) cap the
  ceiling rather than dragging the score below 0 — a wallet that does smart
  money things AND has spam NFTs is still recognized for the smart money
  side.

Score buckets (frontend uses these for color/label):
- 80-100 high       — gold, "smart money / long-term native / well-credentialed"
- 60-79  good       — gold dim
- 40-59  neutral    — ink, default
- 20-39  low        — gray, "shallow / hunter / low-conviction"
- 0-19   poor       — red, "sybil candidate / churn / spam-only"
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Archetype weight table — positive contributions add, negative subtract from
# the final score. Numbers are tuned against test wallets:
#   Vitalik         ≈ 85-95  (smart_money + long_term + multi_chain)
#   Active farmer   ≈ 35-50  (testnet_farmer + airdrop_hunter)
#   Fresh wallet    ≈ 15-30  (fresh_wallet, low everything else)
#   Sybil candidate ≈  5-15  (sybil + spam)

ARCHETYPE_WEIGHTS: dict[str, int] = {
    # Positive signals — sophistication, conviction, breadth
    "smart_money":          22,
    "long_term_holder":     16,
    "multi_chain_native":   12,
    "stablecoin_native":     8,
    "bridge_heavy":          5,
    "nft_flipper":           3,   # at least it's deliberate behavior
    # Neutral / mixed
    "degen":                 0,
    "fresh_wallet":         -2,   # penalty for thin track record
    # Negative — noise, low conviction, suspect
    "airdrop_hunter":      -10,
    "testnet_farmer":       -6,   # less harsh than airdrop_hunter, testnet skill is real
    "burner_wallet":       -12,
    "spam_exposed":         -3,   # not the wallet's fault, light penalty
    "high_revert_user":     -8,
    "sybil_candidate":     -25,
}


@dataclass
class ScoreContribution:
    """One line item in the score breakdown."""
    label: str
    delta: int          # signed contribution
    detail: str = ""    # human-readable rationale


@dataclass
class ReputationScore:
    """Composite 0-100 reputation with full transparency."""
    score: int                                          # final clamped value
    bucket: str                                         # high / good / neutral / low / poor
    raw_score: int = 0                                  # before clamping (for debugging)
    contributions: list[ScoreContribution] = field(default_factory=list)


def _bucket_for(score: int) -> str:
    if score >= 80:
        return "high"
    if score >= 60:
        return "good"
    if score >= 40:
        return "neutral"
    if score >= 20:
        return "low"
    return "poor"


def compute_reputation(digest) -> ReputationScore:  # `digest` typed as WalletDigest, avoid import cycle
    """Compute composite reputation. Caller passes a populated WalletDigest."""
    contribs: list[ScoreContribution] = []

    # ---- Base score ---------------------------------------------------------
    # Everyone starts at 50 (neutral). Signals push up or down from there.
    base = 50
    contribs.append(ScoreContribution("baseline", 50, "neutral starting point"))

    # ---- Archetype contributions -------------------------------------------
    # Each archetype adds its weight scaled by confidence. A "tentative"
    # signal at 0.4 confidence contributes less than a "strong" signal at 0.95.
    for arche in digest.archetypes:
        weight = ARCHETYPE_WEIGHTS.get(arche.name, 0)
        if weight == 0:
            continue
        scaled = round(weight * arche.confidence)
        if scaled == 0:
            continue
        contribs.append(ScoreContribution(
            label=f"archetype:{arche.name}",
            delta=scaled,
            detail=f"{arche.bucket} ({arche.confidence:.2f}) × {weight:+d}",
        ))

    # ---- Wallet age bonus --------------------------------------------------
    # Track record matters. Diminishing returns past 2 years.
    age = digest.wallet_age_days
    if age >= 730:
        contribs.append(ScoreContribution("age:veteran", 8, f"{age} days old (≥2 years)"))
    elif age >= 365:
        contribs.append(ScoreContribution("age:established", 5, f"{age} days old (≥1 year)"))
    elif age >= 90:
        contribs.append(ScoreContribution("age:settled", 2, f"{age} days old"))
    elif age < 14 and digest.total_txs >= 3:
        contribs.append(ScoreContribution("age:fresh", -3, f"only {age} days old"))

    # ---- Activity volume ---------------------------------------------------
    # Wallets with substantive history are more interesting than 5-tx ghosts.
    # We log-scale to avoid runaway scores.
    if digest.total_txs >= 500:
        contribs.append(ScoreContribution("activity:deep", 6, f"{digest.total_txs} total txs"))
    elif digest.total_txs >= 100:
        contribs.append(ScoreContribution("activity:active", 3, f"{digest.total_txs} total txs"))
    elif digest.total_txs < 5:
        contribs.append(ScoreContribution("activity:thin", -5, f"only {digest.total_txs} txs"))

    # ---- Funding source signal ---------------------------------------------
    # CEX deposit = real human entry point (positive). Pure airdrop_claim
    # funding = either farmer or recipient with no skin (slight negative).
    if digest.funding_source == "cex_deposit":
        contribs.append(ScoreContribution("funding:cex", 3, "funded from CEX (real-money entry)"))
    elif digest.funding_source == "airdrop_claim":
        contribs.append(ScoreContribution("funding:claim", -2, "first inflow was a claim"))
    # "bridge" funding is neutral — could be CEX→L1→bridge or pure farming.

    # ---- Error rate penalty ------------------------------------------------
    # Reverts happen, but a wallet with chronically high error rate is either
    # a bot, a careless user, or stuck in failed mints. Penalize past a
    # threshold.
    if digest.total_txs >= 20 and digest.error_rate >= 0.20:
        penalty = round(min(digest.error_rate * 20, 8))
        contribs.append(ScoreContribution(
            "errors:chronic", -penalty,
            f"{digest.error_rate*100:.0f}% revert rate over {digest.total_txs} txs",
        ))

    # ---- Mainnet-vs-testnet ratio ------------------------------------------
    # A wallet that's all testnet with ~0 mainnet activity is almost certainly
    # a farming wallet. We already credit testnet_farmer archetype, but the
    # ratio itself is also evidence.
    mn = len(digest.mainnet_chains_active)
    tn = len(digest.testnet_chains_active)
    if mn == 0 and tn >= 2:
        contribs.append(ScoreContribution(
            "ratio:testnet_only", -6,
            f"active on {tn} testnets, 0 mainnets",
        ))
    elif mn >= 3 and tn == 0:
        contribs.append(ScoreContribution(
            "ratio:mainnet_only", 3,
            f"mainnet-native ({mn} chains)",
        ))

    # ---- Spam NFT exposure (cosmetic, light penalty) -----------------------
    # The archetype already covered the broad case. Here we apply an extra
    # tiny nudge if exposure is very high (>50 spam drops), which usually
    # means the wallet has been air-dropped onto for a long time → indicator
    # of wallet age and surface-area, not a real wallet flaw.
    spam = digest.tokens.spam_nft_count if hasattr(digest, "tokens") else 0
    if spam >= 50:
        contribs.append(ScoreContribution(
            "exposure:heavy_spam", -2,
            f"{spam} likely-spam NFTs (large attack surface)",
        ))

    # ---- Final score -------------------------------------------------------
    raw = base + sum(c.delta for c in contribs if c.label != "baseline")
    # `base` is the contribution labeled "baseline" — we already counted it,
    # so don't double-add. Keep the raw value for transparency.
    raw = sum(c.delta for c in contribs)
    score = max(0, min(100, raw))
    return ReputationScore(
        score=score,
        bucket=_bucket_for(score),
        raw_score=raw,
        contributions=contribs,
    )


def reputation_to_prompt_lines(rep: ReputationScore) -> list[str]:
    """Render the score as compact prompt context for the analyst."""
    out = [
        f"### Reputation score: **{rep.score}/100** ({rep.bucket})",
        "Top contributions (signed):",
    ]
    # Sort by absolute magnitude so the most influential signals are listed
    # first — the LLM can ground its narrative in these.
    sorted_contribs = sorted(rep.contributions, key=lambda c: abs(c.delta), reverse=True)
    for c in sorted_contribs[:8]:
        if c.delta == 0 or c.label == "baseline":
            continue
        sign = "+" if c.delta > 0 else ""
        out.append(f"- {c.label}: {sign}{c.delta} ({c.detail})")
    out.append("")
    return out
