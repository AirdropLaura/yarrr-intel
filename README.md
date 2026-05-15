# Yarrr.Intel

> Paste any wallet. Instantly understand what it actually does.

AI Wallet Intelligence — feed any EVM address, and Yarrr.Intel reads its
on-chain history across 5 chains and tells you what the wallet *is*: airdrop
hunter, smart-money DeFi user, dormant whale, NFT trader, MEV bot. Not just
balances. Not another portfolio tracker.

Powered by [Xiaomi MiMo](https://platform.xiaomimimo.com/) V2.5.

**Live:** https://yarrr-node.com

## Why

Block explorers show you data. They don't tell you what it means. Looking at
Etherscan, you see hashes, gas, timestamps. You don't see *who this wallet is*.

Yarrr.Intel does the interpretation. We compress 250 transactions across 5
chains into a 500-token digest, then ask MiMo V2.5 to write the kind of
summary a senior on-chain analyst would write — concise, evidence-based,
free of bro-hype.

## Sample output (vitalik.eth)

```
TL;DR
Sophisticated multi-chain DeFi operator actively engaging protocols across
all five major EVM chains, with concentrated Uniswap V3 liquidity activity
on Base and heavy contract-level interactions on Ethereum and L2s.

Behavior tags
multi_chain · defi_user · smart_money · lp_provider · high_activity · governance_voter

Notable findings
- Repeated targeting of unverified contract 0xe67362…e25f across 3 L2s — likely a single protocol or aggregator the wallet uses heavily
- Base DEX activity is exclusively Uniswap V3, suggesting deliberate LP positioning rather than opportunistic swaps
- Near-zero direct transfers (1 of 250 tx) — capital flows entirely through contracts
```

## What the report covers

- **TL;DR** — one vivid sentence on what the wallet is
- **Behavioral profile** — what kind of operator runs this wallet
- **Behavior tags** — `airdrop_hunter`, `smart_money`, `dormant`, `bridge_user`, etc.
- **Chain footprint** — primary hub vs. peripheral chains
- **Notable findings** — recent unusual moves, dormant→active shifts, suspicious patterns
- **Risks & approvals** — high error rates, repeated reverts, unverified counterparties
- **Bottom line** — one paragraph you could send to a friend

## Stack

- **Frontend** — Next.js 14, Tailwind, dark + gold elegant theme, streaming SSE
- **Backend** — FastAPI (Python 3.11), in-memory cache (5-min TTL)
- **On-chain data** — Etherscan V2 (Ethereum, Polygon, Arbitrum) + Blockscout (Base, Optimism)
- **Inference** — Xiaomi MiMo V2.5
- **Deployment** — single VPS, nginx, Let's Encrypt, systemd

## Privacy

We never store wallet addresses, queries, or analysis output. The only
persistence is a 5-minute in-memory cache to deduplicate concurrent requests.

## Status

Beta. Free during beta. Built and operated by [@AirdropLaura](https://github.com/AirdropLaura).

## License

MIT — see [LICENSE](LICENSE).
