# Yarrr.Tech

> AI co-pilot for Web3 testnet operators, node runners, and airdrop builders.

Paste any Web3 ops failure — node panic, tx revert, RPC timeout, faucet error,
MetaMask popup hang, Docker port conflict, dependency mismatch, smart contract
revert. Get the root cause and exact fix commands.

Powered by [Xiaomi MiMo](https://platform.xiaomimimo.com/) V2.5.

**Live:** https://yarrr-node.com

## Why

Web3 ops is mostly debugging. Whether you're running a validator at 3am, hunting
airdrops across ten testnets, or wiring up a Foundry script, you spend more
time staring at cryptic errors than building.

Most of those errors have known fixes — the knowledge is just scattered across
Discord threads, GitHub issues, forum posts, and outdated docs. Yarrr.Tech
turns one paste-bin into a focused diagnostic tool: one prompt, one root cause,
one set of commands to try. No hunting through 47 tabs.

## What it troubleshoots

- **Node & validator logs** — Cosmos SDK, CometBFT, Tendermint, Substrate, EVM clients
- **RPC errors** — eth_call failures, JSON-RPC malformed, rate limits, 429/502/504
- **Failed testnet transactions** — reverts, nonce mismatch, gas estimation, replacement underpriced
- **MetaMask & wallet automation** — Playwright/Puppeteer popup races, chain id, user-rejected
- **Faucets** — rate limits, captcha, IP bans, drip queues, eligibility checks
- **Bridges / swaps / mints** — LayerZero, Wormhole, Hop, Uniswap, NFT mint reverts, allowance issues
- **Docker / systemd / Linux services** — restart loops, port conflicts, OOMKilled, permission denied
- **npm / pnpm / yarn / Python** — peer-dep conflicts, module not found, resolver failures
- **Smart contracts** — decoded revert reasons, ABI mismatches, Foundry/Hardhat, Solidity compiler
- **Airdrop workflows** — eligibility, claim transactions, proof generation, signature mismatch

Node ops is the strongest single use case, but the product is broader by design.

## Stack

- **Frontend** — Next.js 14 (App Router), Tailwind, shadcn-style components, dark + gold elegant theme
- **Backend** — FastAPI (Python 3.11), streaming SSE, MiMo client wrapper
- **Inference** — Xiaomi MiMo V2.5 (`mimo-v2.5` for reasoning, `mimo-v2-flash` for quick suggestions)
- **Deployment** — Single VPS (Ubuntu 24.04) + nginx + Let's Encrypt + systemd
- **Domain** — `yarrr-node.com`

## Status

Beta. Free during beta. Built and operated by [@AirdropLaura](https://github.com/AirdropLaura).

## License

MIT — see [LICENSE](LICENSE).
