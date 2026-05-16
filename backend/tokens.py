"""Token reference data — stablecoins, LP tokens, spam patterns, etc.

Curated address lookups for Layer 2 signal extraction. Lowercase addresses.
We deliberately keep this small and high-signal — better to be useful for
top-tier coverage than exhaustive but noisy.
"""
from __future__ import annotations


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


# Heuristic spam-NFT signals. We don't maintain a blocklist (impossible to
# keep current), but we flag common patterns scammers use to inflate inbox.
SPAM_NFT_NAME_KEYWORDS = (
    "visit", "claim", "airdrop", "reward", "prize", "voucher",
    "free", "$", "http", ".com", ".io", ".xyz", ".app",
    "winner", "exclusive", "vip", "🎁", "🎉", "💰",
)


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
    """Heuristic spam NFT detector. Conservative — false positives hurt more
    than false negatives here because we don't want to label legit projects."""
    haystack = f"{name} {symbol}".lower()
    hits = sum(1 for kw in SPAM_NFT_NAME_KEYWORDS if kw.lower() in haystack)
    return hits >= 1
