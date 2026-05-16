"""Asset trust / confidence engine.

Layered classification for ERC20 holdings. Goal: stop the UI from quoting
"$2.1K" with a straight face when the underlying token has zero verified
liquidity, no curation, and 5 holders.

Three-tier output:
- TRUSTED   — curated address match (USDC, USDT, DAI, WETH, stETH, OP, ARB,
              real native tokens). High confidence the symbol means what it
              says and an open market exists.
- UNCERTAIN — unknown contract that didn't trip spam heuristics. Could be
              real (a new protocol) or could be artificial (illiquid token
              dressed up to look real). UI must communicate "we can't
              confirm this is sellable".
- SPAM      — heuristic match (URL in name, hostile TLD, claim/airdrop
              keywords). Hidden by default in UI.

Each classification ships with a 0-100 confidence score and a list of
human-readable reason strings the UI / LLM can surface verbatim.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .tokens import (
    is_stablecoin,
    is_lp_token,
    is_lst_token,
    looks_like_spam_token,
)


# ---------------------------------------------------------------------------
# Curated trusted token registry — chain-scoped lowercase contract → symbol.
# Goal: cover blue-chip assets where the user can be told "yes this is real
# and sellable" without further analysis. Be conservative; if in doubt, omit.
# ---------------------------------------------------------------------------

_BLUECHIPS_BY_CHAIN: dict[str, dict[str, str]] = {
    # === Ethereum mainnet ===
    "ethereum": {
        # Stablecoins (also covered by tokens.STABLECOINS but listed for completeness)
        "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": "USDC",
        "0xdac17f958d2ee523a2206206994597c13d831ec7": "USDT",
        "0x6b175474e89094c44da98b954eedeac495271d0f": "DAI",
        "0x4fabb145d64652a948d72533023f6e7a623c7c53": "BUSD",
        "0x853d955acef822db058eb8505911ed77f175b99e": "FRAX",
        "0x6c3ea9036406852006290770bedfcaba0e23a0e8": "PYUSD",
        # Wrapped & LSTs
        "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": "WETH",
        "0xae7ab96520de3a18e5e111b5eaab095312d7fe84": "stETH",
        "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0": "wstETH",
        "0xae78736cd615f374d3085123a210448e74fc6393": "rETH",
        "0xbe9895146f7af43049ca1c1ae358b0541ea49704": "cbETH",
        "0x5e8422345238f34275888049021821e8e08caa1f": "frxETH",
        "0xac3e018457b222d93114458476f3e3416abbe38f": "sfrxETH",
        # DeFi blue chips
        "0x514910771af9ca656af840dff83e8264ecf986ca": "LINK",
        "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984": "UNI",
        "0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9": "AAVE",
        "0xd533a949740bb3306d119cc777fa900ba034cd52": "CRV",
        "0xc00e94cb662c3520282e6f5717214004a7f26888": "COMP",
        "0x6b3595068778dd592e39a122f4f5a5cf09c90fe2": "SUSHI",
        "0xba100000625a3754423978a60c9317c58a424e3d": "BAL",
        "0xc944e90c64b2c07662a292be6244bdf05cda44a7": "GRT",
        "0x111111111117dc0aa78b770fa6a738034120c302": "1INCH",
        "0x0bc529c00c6401aef6d220be8c6ea1667f6ad93e": "YFI",
        # Major L2 / app tokens bridged on ETH
        "0x4200000000000000000000000000000000000042": "OP",  # actually L2 native; included for safety
    },
    # === Arbitrum ===
    "arbitrum": {
        "0xaf88d065e77c8cc2239327c5edb3a432268e5831": "USDC",
        "0xff970a61a04b1ca14834a43f5de4533ebddb5cc8": "USDC.e",
        "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9": "USDT",
        "0xda10009cbd5d07dd0cecc66161fc93d7c9000da1": "DAI",
        "0x82af49447d8a07e3bd95bd0d56f35241523fbab1": "WETH",
        "0x912ce59144191c1204e64559fe8253a0e49e6548": "ARB",
        "0xf97f4df75117a78c1a5a0dbb814af92458539fb4": "LINK",
        "0xfa7f8980b0f1e64a2062791cc3b0871572f1f7f0": "UNI",
        "0xba5ddd1f9d7f570dc94a51479a000e3bce967196": "AAVE",
    },
    # === Base ===
    "base": {
        "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": "USDC",
        "0x50c5725949a6f0c72e6c4a641f24049a917db0cb": "DAI",
        "0x4200000000000000000000000000000000000006": "WETH",
        "0xc1cba3fcea344f92d9239c08c0568f6f2f0ee452": "wstETH",
    },
    # === Optimism ===
    "optimism": {
        "0x0b2c639c533813f4aa9d7837caf62653d097ff85": "USDC",
        "0x7f5c764cbc14f9669b88837ca1490cca17c31607": "USDC.e",
        "0x94b008aa00579c1307b0ef2c499ad98a8ce58e58": "USDT",
        "0xda10009cbd5d07dd0cecc66161fc93d7c9000da1": "DAI",
        "0x4200000000000000000000000000000000000006": "WETH",
        "0x4200000000000000000000000000000000000042": "OP",
        "0x350a791bfc2c21f9ed5d10980dad2e2638ffa7f6": "LINK",
        "0x76fb31fb4af56892a25e32cfc43de717950c9278": "AAVE",
    },
    # === Polygon ===
    "polygon": {
        "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359": "USDC",
        "0x2791bca1f2de4661ed88a30c99a7a9449aa84174": "USDC.e",
        "0xc2132d05d31c914a87c6611c10748aeb04b58e8f": "USDT",
        "0x8f3cf7ad23cd3cadbd9735aff958023239c6a063": "DAI",
        "0x7ceb23fd6bc0add59e62ac25578270cff1b9f619": "WETH",
        "0x0d500b1d8e8ef31e21c99d1db9a6444d3adf1270": "WMATIC",
    },
    # === BSC ===
    "bsc": {
        "0x55d398326f99059ff775485246999027b3197955": "USDT",
        "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d": "USDC",
        "0xe9e7cea3dedca5984780bafc599bd69add087d56": "BUSD",
        "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c": "WBNB",
        "0x2170ed0880ac9a755fd29b2688956bd959f933f8": "ETH",  # BEP-20 ETH
    },
    # === Avalanche ===
    "avalanche": {
        "0xb97ef9ef8734c71904d8002f8b6bc66dd9c48a6e": "USDC",
        "0xc7198437980c041c805a1edcba50c1ce5db95118": "USDT",
        "0xd586e7f844cea2f87f50152665bcbc2c279d8d70": "DAI",
        "0xb31f66aa3c1e785363f0875a1b74e27b85fd66c7": "WAVAX",
    },
}


# Canonical chain alias (some sources call it "berachain", "blast-mainnet", etc).
# Lowercase, matches ChainData.chain values used in chain.py.
_CHAIN_ALIAS: dict[str, str] = {
    "eth": "ethereum",
    "arb": "arbitrum",
    "op": "optimism",
    "matic": "polygon",
    "avax": "avalanche",
}


def _canon_chain(chain: str) -> str:
    c = (chain or "").lower().strip()
    return _CHAIN_ALIAS.get(c, c)


def is_bluechip(chain: str, contract: str) -> str | None:
    """Returns canonical symbol if the address is a curated blue-chip asset."""
    bc = _BLUECHIPS_BY_CHAIN.get(_canon_chain(chain), {})
    return bc.get((contract or "").lower())


# ---------------------------------------------------------------------------
# Trust classification output
# ---------------------------------------------------------------------------

@dataclass
class TrustVerdict:
    """Classification verdict for a single token holding.

    `confidence` is 0-100 — useful for sort order and progress bars.
    `tier` is the human-facing bucket: "trusted" / "uncertain" / "spam".
    `verdict_short` is a one-line plain-English summary.
    `reasons` are bullet-style reasons the UI can surface verbatim.
    """
    tier: str                     # "trusted" | "uncertain" | "spam"
    confidence: int               # 0–100
    verdict_short: str            # one-line summary, plain English
    reasons: list[str] = field(default_factory=list)


# Confidence score targets per tier — keep these stable so UI bars match
# user mental model. We blend tier + reason count to get a final score.
_CONF_TRUSTED_BASE = 92
_CONF_UNCERTAIN_BASE = 45
_CONF_SPAM_BASE = 8


def classify_token(
    *,
    chain: str,
    contract: str,
    name: str,
    symbol: str,
    is_native: bool = False,
    is_testnet: bool = False,
    holders_count: int | None = None,    # optional, future enrichment
    market_cap_usd: float | None = None, # optional, future enrichment
    has_liquidity: bool | None = None,   # optional, future enrichment
) -> TrustVerdict:
    """Classify a token into trusted / uncertain / spam with reasons.

    The function is pure — it only inspects the inputs. Future hooks for
    holders_count / market_cap / liquidity exist for when we wire a price
    oracle (CoinGecko, DefiLlama) or RPC `balanceOf` enumeration.

    `is_testnet` softens the bluechip-impersonation rule — on testnets, a
    token symbol like "DAI" with an unrecognized contract is almost always
    a faucet, not a scam. We mark it uncertain with explicit testnet phrasing
    so the user understands "this is testnet play money, not real DAI."
    """
    # Native chain coin (ETH, MATIC, BNB, AVAX...) — always trusted
    if is_native:
        return TrustVerdict(
            tier="trusted",
            confidence=98,
            verdict_short="Native chain asset with verified market liquidity.",
            reasons=["native chain currency"],
        )

    contract_l = (contract or "").lower()
    chain_canon = _canon_chain(chain)

    # === Spam check first — once flagged, no upgrade path ===
    if looks_like_spam_token(name, symbol):
        reasons = ["matches spam heuristic (suspicious name pattern)"]
        # Add specifics where possible
        haystack = f"{name or ''} {symbol or ''}".lower()
        if any(u in haystack for u in ("www.", "http", "://", "bit.ly", "t.me/")):
            reasons.append("contains URL in token name (typical scam vector)")
        if "[" in (name or "") and "]" in (name or ""):
            reasons.append("uses brackets to embed promotional text")
        if "airdrop" in haystack or "claim" in haystack:
            reasons.append("uses airdrop / claim language to bait approvals")
        return TrustVerdict(
            tier="spam",
            confidence=_CONF_SPAM_BASE,
            verdict_short="Likely spam or phishing token. Do not interact.",
            reasons=reasons,
        )

    # === Curated bluechip — highest trust ===
    bc_symbol = is_bluechip(chain_canon, contract_l)
    if bc_symbol:
        return TrustVerdict(
            tier="trusted",
            confidence=_CONF_TRUSTED_BASE,
            verdict_short=f"Verified blue-chip asset on {chain_canon}.",
            reasons=[
                "contract is on the curated trusted list",
                "established market depth and liquidity",
            ],
        )

    # === Stablecoin (registered, but not in chain-scoped bluechip list) ===
    if is_stablecoin(contract_l):
        return TrustVerdict(
            tier="trusted",
            confidence=88,
            verdict_short="Stablecoin contract — verified.",
            reasons=["matches a known stablecoin contract address"],
        )

    # === LST recognized by symbol but unknown contract ===
    if is_lst_token(symbol or ""):
        return TrustVerdict(
            tier="uncertain",
            confidence=60,
            verdict_short="Looks like a liquid staking token, but contract is not on our verified list.",
            reasons=[
                "symbol matches known LST naming pattern",
                "contract not in curated registry — may be a fork or imitation",
            ],
        )

    # === LP token ===
    if is_lp_token(symbol or ""):
        return TrustVerdict(
            tier="uncertain",
            confidence=55,
            verdict_short="Liquidity-pool token. Value depends on the underlying pair.",
            reasons=[
                "appears to be a DEX LP receipt token",
                "real value depends on the underlying pool — not a standalone asset",
            ],
        )

    # === Default: uncertain — unknown contract, no spam signals ===
    reasons = [
        "contract not on our verified registry",
        "no confirmed market depth or liquidity check available",
    ]
    confidence = _CONF_UNCERTAIN_BASE

    # Symbol shape penalties — long, all-caps, or pseudo-branded names
    sym = (symbol or "").strip()
    if len(sym) > 12:
        reasons.append("unusually long symbol (>12 chars)")
        confidence -= 5
    if len(sym) <= 1 or len(sym) > 20:
        reasons.append("symbol length outside typical token range")
        confidence -= 5

    # Name-mimics-bluechip detection — fake "USDC" / "ETH" / "BTC" tokens
    bluechip_symbols = {"USDC", "USDT", "DAI", "WETH", "ETH", "BTC", "WBTC", "BNB", "ARB", "OP", "MATIC"}
    if sym.upper() in bluechip_symbols:
        # Symbol matches a bluechip but the contract did NOT match curated list.
        # On testnets this is normal (faucet tokens). On mainnet it's almost
        # always an impersonation scam.
        if is_testnet:
            return TrustVerdict(
                tier="uncertain",
                confidence=55,
                verdict_short=f"Testnet '{sym.upper()}' faucet token — not real {sym.upper()}, no real-world value.",
                reasons=[
                    f"symbol '{sym.upper()}' on a testnet — typically a faucet token",
                    "testnet assets have no economic value on mainnet",
                ],
            )
        # Mainnet impersonation
        reasons.append(
            f"symbol '{sym.upper()}' matches a major asset, but contract is unverified — possible impersonation"
        )
        confidence = 18
        return TrustVerdict(
            tier="spam",
            confidence=confidence,
            verdict_short=f"Token symbol mimics '{sym.upper()}' but the contract is not the official one. Likely scam.",
            reasons=reasons,
        )

    # Future enrichment: holders, market cap, liquidity. Hook ready.
    if holders_count is not None and holders_count < 100:
        reasons.append(f"only {holders_count} holders — extremely thin distribution")
        confidence -= 10
    if market_cap_usd is not None and market_cap_usd < 1000:
        reasons.append("no meaningful market cap detected")
        confidence -= 10
    if has_liquidity is False:
        reasons.append("no liquidity pool found on major DEXes")
        confidence -= 15

    confidence = max(15, min(75, confidence))

    return TrustVerdict(
        tier="uncertain",
        confidence=confidence,
        verdict_short="Unverified token. Sellable market value cannot be confirmed.",
        reasons=reasons,
    )


def summarize_holdings_trust(
    holdings: list[dict],
) -> dict:
    """Aggregate trust stats across a wallet's holdings.

    Used by the profiler to produce a digest-level summary the LLM and UI
    can both consume. `holdings` items must already include `trust_tier`.
    """
    trusted = sum(1 for h in holdings if h.get("trust_tier") == "trusted")
    uncertain = sum(1 for h in holdings if h.get("trust_tier") == "uncertain")
    spam = sum(1 for h in holdings if h.get("trust_tier") == "spam")
    total = trusted + uncertain + spam

    real_token_count = trusted + uncertain  # everything user might actually own
    spam_ratio = (spam / total) if total else 0.0

    headline = "No tokens detected in recent transfer history."
    if total > 0:
        if trusted == 0 and uncertain == 0:
            headline = "Wallet contains only suspicious or spam tokens — likely an airdrop-bombed address."
        elif spam_ratio >= 0.7:
            headline = "Wallet is heavily flooded with spam airdrops; only a small fraction of tokens are real."
        elif trusted >= 1 and uncertain == 0 and spam == 0:
            headline = "Clean wallet — only verified blue-chip assets detected."
        elif trusted >= 1:
            headline = f"{trusted} verified asset{'s' if trusted != 1 else ''} alongside {uncertain} unverified token{'s' if uncertain != 1 else ''}."
        else:
            headline = f"{uncertain} unverified token{'s' if uncertain != 1 else ''} detected — none on our trusted list."

    return {
        "trusted_count": trusted,
        "uncertain_count": uncertain,
        "spam_count": spam,
        "real_token_count": real_token_count,
        "spam_ratio": round(spam_ratio, 3),
        "headline": headline,
    }
