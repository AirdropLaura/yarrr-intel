# Yarrr.Tech

> AI-native diagnostics for testnet & validator node operators.

Paste a stack trace or log file. Get the root cause and the exact fix commands.
Powered by [Xiaomi MiMo](https://platform.xiaomimimo.com/) V2.5.

**Live:** https://yarrr-node.com

## Why

Running testnets and validator nodes means staring at cryptic errors, peer
timeouts, consensus state corruption, and dependency mismatches at 3am. Most of
those errors have known fixes — but the knowledge is scattered across Discord
threads, GitHub issues, and forum posts.

Yarrr.Tech turns a paste-bin and a chat box into a focused diagnostic tool: one
prompt, one root cause, one set of commands to run. No hunting through 47 tabs.

## Stack

- **Frontend** — Next.js 14 (App Router), Tailwind, shadcn/ui
- **Backend** — FastAPI (Python 3.11)
- **Inference** — Xiaomi MiMo V2.5 (`mimo-v2.5` for reasoning, `mimo-v2-flash` for quick suggestions)
- **Deployment** — Single VPS (Ubuntu 24.04) + nginx + Let's Encrypt
- **Domain** — `yarrr-node.com`

## Status

Currently in active development. Holding page live; full app deploying soon.

## License

MIT — see [LICENSE](LICENSE).
