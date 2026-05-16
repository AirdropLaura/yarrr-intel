# Yarrr.Tech — Product Direction

> AI-native onchain identity intelligence engine.
> Built by Bastiar.

## North Star

The product answers **"What kind of wallet is this?"** — not "What tokens does
this wallet hold?". We are not a portfolio dashboard. We are an investigator.

## Positioning

We do **not** compete with Debank / Zerion / Zapper.
We compete in: **AI-powered onchain behavioral intelligence**.

The moat is the interpretation layer — compressing thousands of transactions
across many chains into a single, sharp behavioral judgement.

---

## Architecture

Three logical layers, kept clean.

### Layer 1 — Raw Ingestion

**Goal:** breadth-first multichain activity collection.

Mainnets supported:
- Ethereum, Polygon, Arbitrum, Optimism, Base
- BSC, Linea, Scroll, Blast, Avalanche
- Mantle, World Chain, opBNB, Gnosis, Sonic
- Future: Berachain, Monad, Soneium, Abstract, Starknet

Testnets (key differentiator — most tools ignore these):
- Sepolia, Holesky, Base Sepolia, Arbitrum Sepolia, Optimism Sepolia
- BSC Testnet, Polygon Amoy, Linea Sepolia, Scroll Sepolia, Blast Sepolia

Ingestion targets per chain:
- Native balance + tx count
- Last N normal transactions
- Internal txs (Phase 2)
- ERC20 / NFT transfers (Phase 2)
- Approvals (Phase 2)
- Bridge events (Phase 2)
- Failed txs / reverts
- Gas patterns
- First-seen timestamps

Provider strategy:
- **Etherscan V2** primary — single API key covers 15+ chains by `chain_id`
- **Blockscout** for chains outside Etherscan V2 (Base early, Optimism, Berachain)
- **Native RPC** fallback for ENS / balance / chain-specific reads
- All providers MUST be pluggable. Adding a chain = adding one row to the
  registry, not refactoring core logic.

### Layer 2 — Behavioral Compression

**This is the most important layer.** We never feed raw transactions to the LLM.

Inputs: raw `ChainData[]` per chain.
Outputs: a 300-800 token intelligence digest containing:

Quantitative signals:
- Tx frequency, active days, dormant periods
- Per-chain distribution + chain hopping pattern
- Bridge usage count + bridges used
- DEX preferences (router-level)
- NFT activity profile (mint vs trade vs flip)
- Approval risk (unlimited approvals to unknown counterparties)
- Revert ratio
- Wallet age (first tx → now)
- Funding source heuristic (CEX deposit, faucet, bridge inbound)
- Average gas profile + activity bursts
- Stablecoin usage
- Testnet participation ratio

Behavioral tags + archetype candidates with confidence scores:
```
fresh_wallet
airdrop_hunter
smart_money
nft_flipper
sybil_candidate
degen
bridge_heavy
burner_wallet
long_term_holder
stablecoin_native
testnet_farmer
multi_chain_native
spam_exposed
high_revert_user
```

Risk markers:
- High revert rate
- Unlimited approvals to unverified contracts
- Spam NFT exposure
- Dormant → sudden burst (compromise signal)
- Funding from sanctioned addresses (Phase 3)

Timeline summary:
- Phase boundaries (active, dormant, re-engaged)
- Notable events (first DEX swap, first bridge, etc.)

### Layer 3 — AI Reasoning

LLM is an analyst, not an assistant.

Prompt persona: **senior blockchain intelligence analyst** writing a brief for
a client. Concise, evidence-based, no hype, no bullet spam.

Output structure (every analysis):
1. **TL;DR** — one vivid sentence
2. **Wallet archetype** — primary + secondary with confidence
3. **Risk notes** — concrete signals only
4. **Behavioral summary** — 2-3 paragraphs of interpretation
5. **Timeline evolution** — what changed over time
6. **Notable findings** — 2-5 sharp observations

Hard rules:
- Use only digest-evident facts, never invent counterparties or events
- Web3 jargon stays English in both ID and EN locales
- No real-person attribution unless the digest names them
- Total ≤ 500 words

---

## Performance Targets

- Deep analysis: 10-20s end-to-end
- Shallow scan: <5s
- Behavioral compression: deterministic, cacheable
- Minimal hallucination via strict digest-only context

---

## Engineering Priorities

1. Reliability (graceful provider failures)
2. Fast ingestion (parallel by chain, rate-limit aware)
3. Strong compression (deterministic profiler)
4. Sharp prompts (analyst-grade)
5. Broad chain support
6. UX polish (last)

Do not prematurely optimize visuals. The intelligence output is the product.

---

## UX Philosophy

The UI should feel: AI-native, investigative, futuristic.
Not: dashboard, trader-terminal, spreadsheet.

Keep it simple. Big input, sharp output, share button.

---

## Roadmap

### Phase 1 — Foundation Shift ✓
- [x] Chain expansion: 5 → 16 mainnets + 10 testnets via Etherscan V2 multichain
- [x] ENS / Basename resolution (ENSIdeas API)
- [x] Profiler v2: archetype scoring engine, funding source heuristic, testnet farming ratio
- [x] Senior-analyst prompt rewrite (TL;DR → archetype → risk → behavioral → timeline → notable)
- [x] Frontend: archetype badge, ENS display, i18n updates, mainnet/testnet split

### Phase 2 — Core Features ✓
- [x] **2a** ERC20 + NFT ingestion (primary mainnets) — stablecoin volume, distinct ERC20s, LP / LST detection, spam NFT heuristic
- [x] **2a** Failed tx pattern analysis — clusters of repeated reverts to same target
- [x] **2a** New archetypes: `stablecoin_native`, `spam_exposed`; `smart_money` upgraded with LP/LST signal; `high_revert_user` upgraded with cluster signal
- [x] **2b** SQLite-backed persistence (`yarrr.db`) — `POST /api/share`, `GET /api/share/{id}`, `GET /api/history/{addr}`
- [x] **2b** Shareable URL (`/a/<id>/`) with full analysis re-render — nginx fall-through, deterministic id
- [x] **2c** Wallet timeline view — bucketed activity periods with chain + category + error rate, frontend visualization (log-scale bars, color-coded)
- [x] **2d** Pluggable provider abstract (`backend/providers/`) — `ChainProvider` ABC, `EtherscanV2Provider`, `BlockscoutProvider`, registry-based dispatch. Adding a chain = one row in registry.

### Phase 3 — Advanced Intelligence (in progress)
- [x] **3.1** Emerging-ecosystem chains: Berachain, Monad, Sonic, Abstract, Taiko, Fraxtal mainnets + 5 testnets via Etherscan V2 (37 chains total — proves pluggable architecture works without code changes for V2-supported chains)
- [x] **3.2** OG image generation — 1200×630 PNG cards via Pillow (no headless browser), `/api/og/<id>.png`, server-rendered HTML at `/a/<id>/` with full OG/Twitter meta, SPA hydrates via `/a/?sid=<id>` for interactive view
- [x] **3.3** Composite reputation score (`backend/reputation.py`) — 0-100 weighted signal: archetype contributions × confidence + age bonus + activity volume + funding source + error penalty + mainnet/testnet ratio. Five buckets (high/good/neutral/low/poor). Surfaced to analyst prompt + frontend semicircle gauge with top-6 contributions + OG card hero stat.
- [x] **3.4** Sybil graph (`backend/cluster.py`) — wallet_funding SQLite table indexes earliest CEX/bridge funding events; cluster query finds wallets sharing source within ±15min window. `GET /api/cluster/<addr>` exposes siblings + delta_seconds. Frontend `ClusterPanel` auto-hides until MIN_CLUSTER_SIZE=2 matches found. Database compounds with usage.
- [x] **3.5** Routescan provider (`backend/providers/routescan.py`) — Etherscan-V1-compatible API surface for Avalanche L1/subnets and other non-V2 EVM chains. Provider registered, framework ready; chains added on demand. Starknet skipped — non-EVM, out of EVM-focused product scope.
- [x] **3.6** Webhook subscriptions (`backend/webhooks.py`) — SQLite-backed wallet subscription table, async background watcher polling every 15 minutes, deterministic state diff (primary archetype, reputation bucket, dormancy, new chains), HTTP POST delivery. Auto-pause after 5 consecutive failures. Endpoints: `POST /api/webhooks`, `GET /api/webhooks`, `DELETE /api/webhooks/{id}`. Idempotent on (address, url).

### Phase 4 — Coverage & Comparative Analysis (v0.10)
- [x] **4.1** Hero copy + system prompt updated to reflect actual coverage (22 mainnets + 15 testnets, not "5 chains")
- [x] **4.2** Dynamic contract name resolver (`backend/contract_names.py`) — 7-stage pipeline: curated dict → SQLite cache → ERC20/NFT name harvest → Etherscan V2 `getsourcecode` → method-selector heuristic → ETH-transfer pattern detection → short-address fallback. Cross-chain token name reuse, TTL 30d hits / 6h misses.
- [x] **4.3** Multi-address comparative analysis — `POST /api/analyze/multi` (2-10 wallets, parallel digest fetch, single comparative LLM call with `MULTI_SYSTEM_PROMPT`). Frontend Single/Multi mode toggle + textarea parsing newline/comma/space.

---

## Mission

Build the best AI-native wallet intelligence engine on the internet. The user
should walk away thinking: *"This AI understands onchain behavior better than
I do."*
