"""Token reference data — stablecoins, LP tokens, spam patterns, etc.

Curated address lookups for Layer 2 signal extraction. Lowercase addresses.
We deliberately keep this small and high-signal — better to be useful for
top-tier coverage than exhaustive but noisy.
"""
from __future__ import annotations

import re


# Stablecoin contracts (USD, EUR, GBP, etc.) on EVM mainnets.
# Used to compute stablecoin exposure and detect "stablecoin_native" archetype.
STABLECOINS: dict[str, str] = {
    # USDT
    "0xdac17f958d2ee523a2206206994597c13d831ec7": "USDT",   # Ethereum
    "0xc7198437980c041c805a1edcba50c1ce5db95118": "USDT",   # Avalanche
    "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9": "USDT",   # Arbitrum
    "0x55d398326f99059ff775485246999027b3197955": "USDT",   # BSC
    "0xc2132d05d31c914a87c6611c10748aeb04b58e8f": "USDT",   # Polygon
    "0x94b008aa00579c1307b0ef2c499ad98a8ce58e58": "USDT",   # Optimism
    # USDC
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": "USDC",   # Ethereum
    "0xaf88d065e77c8cc2239327c5edb3a432268e5831": "USDC",   # Arbitrum
    "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": "USDC",   # Base
    "0x0b2c639c533813f4aa9d7837caf62653d097ff85": "USDC",   # Optimism
    "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359": "USDC",   # Polygon (native)
    "0x2791bca1f2de4661ed88a30c99a7a9449aa84174": "USDC.e", # Polygon (bridged)
    "0xff970a61a04b1ca14834a43f5de4533ebddb5cc8": "USDC.e", # Arbitrum (bridged)
    "0x7f5c764cbc14f9669b88837ca1490cca17c31607": "USDC.e", # Optimism (bridged)
    "0xb97ef9ef8734c71904d8002f8b6bc66dd9c48a6e": "USDC",   # Avalanche (native)
    "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d": "USDC",   # BSC
    # DAI
    "0x6b175474e89094c44da98b954eedeac495271d0f": "DAI",    # Ethereum
    "0xda10009cbd5d07dd0cecc66161fc93d7c9000da1": "DAI",    # Arbitrum, Optimism, Polygon
    "0x50c5725949a6f0c72e6c4a641f24049a917db0cb": "DAI",    # Base
    # FRAX, sUSD, others
    "0x853d955acef822db058eb8505911ed77f175b99e": "FRAX",
    "0x57ab1ec28d129707052df4df418d58a2d46d5f51": "sUSD",
    "0x4fabb145d64652a948d72533023f6e7a623c7c53": "BUSD",
    "0x6c3ea9036406852006290770bedfcaba0e23a0e8": "PYUSD",
}


# Common LP / staking receipt tokens — owning many of these signals DeFi
# sophistication. Pattern-based detection (suffix or prefix in symbol):
LP_TOKEN_PATTERNS = ("LP", "UNI-V2", "UNI-V3", "CAKE-LP", "SLP", "BLP", "PCS-LP")
LST_TOKEN_PATTERNS = ("stETH", "rETH", "cbETH", "wstETH", "frxETH", "sfrxETH", "ezETH", "weETH")


# === Spam token / NFT detection ============================================
# Scoring system. Each match adds points. Threshold ≥ 3 = spam.
# Calibration goal: catch obvious spam without flagging legit DeFi protocols
# whose names look "weird" (e.g. yearn.finance, 1inch.exchange, USDC.e).

# STRONG (3 pts each, single match → spam): URL-like patterns. Real token
# names almost never embed full URLs or shorteners.
_SPAM_URL_PATTERNS = (
    "www.", "http://", "https://", "://",
    "bit.ly", "t.me/", "telegram.me/", "tinyurl", "goo.gl", "ow.ly", "tiny.cc",
    "shorturl",
)

# STRONG (3 pts): multi-word phrases that are basically never in legit names.
_SPAM_PHRASES = (
    "use code", "claim now", "claim your", "your reward", "your prize",
    "winner of", "earn rewards", "to claim", "to redeem",
    "limited time", "exclusive offer", "you won", "you've won", "youve won",
    "claim airdrop", "airdrop claim", "claim base",
    "visit ", "visit:", "click here", "click to",
    "free $", "free token", "free crypto", "free reward",
    "redeem your", "redeem now", "rewards link",
)

# MEDIUM (2 pts): hostile TLDs. Curated to avoid false positives on legit
# DeFi protocols that use TLD-style names (yearn.finance, 1inch.exchange,
# kyber.network, ENS .eth, etc.). Only includes TLDs that are overwhelmingly
# associated with crypto airdrop scams in observed data.
_SPAM_TLDS = (
    ".life", ".cfd", ".top", ".lol", ".fun", ".gift", ".bid",
    ".click", ".live", ".vip", ".cash", ".gives", ".host",
    ".biz", ".info", ".pro", ".sbs", ".buzz", ".wtf",
    ".monster", ".uno", ".best", ".gold", ".free",
)

# SOFT (1 pt each): keyword signals — need 2+ for spam confidence. Word-bound
# prefix match (\bclaim catches "claim", "claims", "claiming") so we don't
# false-positive on substrings like "Acclaim" or "Reclaim".
_SPAM_KEYWORDS_SOFT = (
    "visit", "claim", "reward", "prize", "voucher",
    "winner", "exclusive", "redeem", "giveaway",
)

# MEDIUM (2 pts each): keywords that legit tokens almost never use in name.
# Legit airdrop campaigns name the TOKEN (e.g. "ARB", "OP"), not the
# action ("Project Airdrop Pass"). Boosted from soft tier so single match
# combined with one weak signal (length / "!") trips the threshold.
_SPAM_KEYWORDS_MEDIUM = (
    "airdrop", "freebie", "sweepstake",
)

# SOFT (1 pt each): emoji heavily used in airdrop spam.
_SPAM_EMOJI = ("🎁", "🎉", "💰", "🎯", "✅", "🚀", "⚡", "💎", "🎊", "🪂")


def is_stablecoin(contract: str) -> str | None:
    """Returns the stablecoin symbol if the address is a known stablecoin."""
    return STABLECOINS.get(contract.lower())


def is_lp_token(symbol: str) -> bool:
    s = (symbol or "").upper()
    return any(p in s for p in LP_TOKEN_PATTERNS)


def is_lst_token(symbol: str) -> bool:
    s = symbol or ""
    return any(p.lower() in s.lower() for p in LST_TOKEN_PATTERNS)


def looks_like_spam_nft(name: str, symbol: str) -> bool:
    """Heuristic spam token / NFT detector.

    Scoring approach (threshold ≥ 3 = spam):
    - URL pattern (www., http, ://, bit.ly, t.me/): 3 pts
    - Hostile TLD (.life, .cfd, .top, .vip, etc): 2 pts
    - Spam phrase ("use code", "claim now", "visit "): 3 pts
    - Bracket structure ([...] in name): 1.5 pts
    - Long name (>30 chars): 1 pt
    - Multiple "!" (>=2): 1 pt
    - Soft keyword (visit, claim, airdrop, ...): 1 pt each, word-bounded prefix
    - Spam emoji (🎁, 🎉, 💰, etc): 1 pt each

    Tuned to NOT false-positive on legit DeFi: yearn.finance, 1inch.exchange,
    USDC.e, ChainLink, Aave, etc. all score 0.

    Tuned to catch observed spam: 'WLD [WWW.WLD-ETHEN.LIFE]', 'Use code XYZ',
    'Visit www.fake.cfd', '! RETIK [retikdrop.com]', etc.
    """
    haystack = f"{name or ''} {symbol or ''}".strip()
    if not haystack:
        return False

    lower = haystack.lower()
    score: float = 0.0

    # === STRONG signals (any single match contributes 3 pts) ===
    if any(p in lower for p in _SPAM_URL_PATTERNS):
        score += 3
    if any(phrase in lower for phrase in _SPAM_PHRASES):
        score += 3

    # === MEDIUM (TLD-only, +2) ===
    if any(tld in lower for tld in _SPAM_TLDS):
        score += 2

    # === Structural anomalies ===
    # Bracket pair: real tokens almost never use [...] in name.
    # Common in spam: "WLD [WWW.WLD-ETHEN.LIFE]", "TOKEN [bit.ly/x]"
    if "[" in haystack and "]" in haystack:
        score += 1.5

    # Long names — legit tokens usually <30 chars. Spam packs URLs in.
    if len(haystack) > 30:
        score += 1

    # Multiple exclamation marks — common spam emphasis
    if haystack.count("!") >= 2:
        score += 1

    # === SOFT keywords (word-boundary prefix match) ===
    for kw in _SPAM_KEYWORDS_SOFT:
        # \bclaim matches "claim", "claims", "claiming", "claimed"
        # but NOT "Acclaim", "Reclaim" because the position of "claim" in
        # those words is preceded by a word char ('c' / 'e').
        if re.search(rf"\b{re.escape(kw)}", lower):
            score += 1

    # === MEDIUM keywords (worth 2 pts each — legit tokens basically never
    # use these in their name) ===
    for kw in _SPAM_KEYWORDS_MEDIUM:
        if re.search(rf"\b{re.escape(kw)}", lower):
            score += 2

    # === SOFT emoji ===
    for em in _SPAM_EMOJI:
        if em in haystack:
            score += 1

    return score >= 3


def looks_like_spam_token(name: str, symbol: str) -> bool:
    """Alias of looks_like_spam_nft — same heuristic applies to ERC20 spam."""
    return looks_like_spam_nft(name, symbol)
