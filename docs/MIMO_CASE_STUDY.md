# MiMo Case Study — Yarrr.Tech AI Wallet Intelligence

> A real production application of Xiaomi MiMo V2.5 reasoning to onchain wallet analysis. This document accompanies our application to the **Xiaomi MiMo Orbit 100T Creator Program** and serves as honest documentation for other builders considering MiMo for production reasoning workloads.

**Project:** Yarrr.Tech (`https://yarrr-node.com`)
**Repo:** `github.com/AirdropLaura/yarrr-intel`
**Maintainer:** Bastiar — Telegram [@yarrr23](https://t.me/yarrr23)
**Live since:** April 2026
**Model in production:** `mimo-v2.5` (flagship reasoning) via `https://api.xiaomimimo.com/v1`

---

## 1. Problem Statement

Block explorers (Etherscan, Blockscout) display raw transaction data. Portfolio trackers (Zapper, DeBank) display token balances and dollar values. Neither answers the actual question a serious onchain analyst asks first:

> **"What does this wallet *do*?"**

Is `0xabc...` a smart-money DeFi LP worth copying? An airdrop farm worth ignoring? A sybil cluster worth flagging? A dormant whale that just woke up? A wallet under approval-risk that the user should revoke?

Block explorers can't answer this — they show data, not interpretation. Portfolio trackers can't answer this — they care about price, not behavior. LLM-powered chat-with-blockchain projects can't answer this reliably either, because they ask the model to do *both* the data extraction *and* the reasoning, leaving the model with stale context, hallucinated transactions, and shallow analysis.

Yarrr.Tech splits the problem deterministically:

1. **Onchain capture** is plain HTTP and parsing — no model involvement. Reproducible, rate-limited, transparent.
2. **Behavioral compression** is deterministic Python — 14 archetype detectors, asset-trust resolver, failed-tx clustering. Same inputs, same outputs.
3. **Reasoning** is the only place the model is asked to act, and it's given pre-digested signal — never raw blockchain dumps.

This separation is *why* a reasoning model like MiMo can shine here: we hand it well-structured signal and ask it to write what a senior analyst would write.

## 2. Why MiMo (and not Claude / GPT / Gemini / Kimi)

We tested four candidates on identical wallet digests:

| Criterion | Claude Opus 4.6 | GPT-5.5 | Gemini 3.1 Pro | MiMo V2.5 |
|---|---|---|---|---|
| Reasoning depth on archetype interpretation | Excellent | Strong | Strong | **Excellent** |
| Indonesian language naturalness | Good but translation-feel | OK, occasional Anglicism | Good | **Native, no translation-feel** |
| Tendency to quote raw numbers blindly | Low | Medium | Medium | **Low** |
| Cost per ~3K-token investigator report | High | Medium | Medium | **Low** |
| Latency P50 | 8-15s | 5-10s | 6-12s | **3-12s** |
| OpenAI-compatible API | Via 9Router | Via 9Router | Direct | **Direct, drop-in** |
| Refuses with hedging filler? | Sometimes | Rarely | Sometimes | **Rarely** |

**MiMo earned the production slot for four concrete reasons:**

### 2.1 Reasoning depth on structured numerical data

Wallet archetype interpretation isn't creative writing. It's *reasoning over structured signal*: "Wallet is active on 5 chains, 70% interactions are with DEX routers, 80% gas spent on Arbitrum, 23 spam NFTs received passively, 0 NFTs sent. What is it?" MiMo's reasoning-first design produces fewer filler hedges and more direct verdicts. Where GPT might write *"this could potentially indicate that..."*, MiMo writes *"this is an airdrop-magnet wallet with no active trading behavior."* That directness matters in an analyst tool.

### 2.2 Native Indonesian quality (not translation-ese)

Yarrr.Tech ships ID + EN bilingual. Indonesian users are our primary audience. Other models give us *correct* Indonesian that reads slightly off — formal Bahasa Baku that no Indonesian crypto user actually speaks. MiMo's Indonesian reads natural — it preserves the convention of keeping technical jargon in English (*smart money, swap, bridge, MEV, archetype*) while delivering the surrounding analysis in conversational Indonesian. This was a tipping-point quality difference for us.

### 2.3 Cost efficiency at our output budget

A typical Yarrr.Tech investigator report runs **~3K output tokens** — TL;DR, archetype reasoning, risk classification, asset trust narrative, behavioral timeline, actionable findings. At that output size with frontier-tier pricing, gating the feature behind paywalls or queues becomes inevitable. MiMo's cost profile lets us serve every public request without rationing — which is critical for a free-to-use intel tool.

### 2.4 OpenAI-compatible API

MiMo's API is drop-in OpenAI-compatible at `https://api.xiaomimimo.com/v1`. Migrating from a previous provider in our stack took less than an hour:

```python
from openai import AsyncOpenAI

mimo = AsyncOpenAI(
    base_url="https://api.xiaomimimo.com/v1",
    api_key=os.environ["MIMO_API_KEY"],
)

response = await mimo.chat.completions.create(
    model="mimo-v2.5",
    messages=[
        {"role": "system", "content": INVESTIGATOR_PROMPT},
        {"role": "user", "content": digest_text},
    ],
    max_tokens=4000,
)
```

That's it. No SDK lock-in, no proprietary protocol.

## 3. Production Architecture

```
User → POST /api/analyze {address, lang}
       │
       ├── Layer 1 (deterministic, ~46s floor for full chain sweep)
       │     • 22 mainnets + 15 testnets via Etherscan V2 (single key)
       │     • txlist + txlistinternal + ERC20 + NFT + native balance
       │     • ENS / Basename resolver
       │     • Token bucket rate limiter (4 RPS sustained)
       │     • Asset trust resolver (80+ curated bluechips, 7-level fallback)
       │
       ├── Layer 2 (deterministic, <100ms)
       │     • Wallet digest → ~2KB structured summary
       │     • 14 archetype detectors with confidence + evidence
       │     • Per-token trust tier (trusted / uncertain / spam)
       │     • Failed-tx cluster analysis
       │     • Behavioral signals (funding, age, approval risk)
       │
       └── Layer 3 (MiMo V2.5, 3-12s)
             • Investigator system prompt
             • Bilingual ID/EN
             • Structured output: TL;DR → archetype → risk → assets → timeline → findings
             → Returned to user as markdown
```

The architecture is intentionally rigid about where MiMo is and isn't called. **MiMo never sees raw transaction data.** It sees a well-structured digest and is asked to write analyst prose. This is the cleanest ratio of "trust the model where it shines, do everything else deterministically."

## 4. Prompt Engineering — Investigator Tone

Early iterations of our prompt produced reports that quoted raw numbers without context:

> Wallet holds 30,000 DAI on Sepolia and 2.1K ERC on Berachain.

That's the failure mode we shipped to fix. The current production system prompt instructs MiMo to behave as a **senior onchain investigator**:

```
You are a senior onchain analyst. Your job is to interpret wallet
behavior, not list numbers.

Asset trust rules:
- Trusted-tier holdings: state amount + chain.
- Uncertain-tier holdings: state amount + chain + caveat
  ("sellable market value cannot be confirmed", "testnet faucet
  token — no real-world value", etc).
- Spam-tier holdings: do NOT quote dollar values. Refer to them as
  passive spam reception. Warn against approving.

Tone: direct, evidence-based, free of hedging filler. If the data
is ambiguous, say so explicitly.
```

The behavioral phrasing library was tuned against real wallets. Sample outputs from the production system on a real test wallet:

> **Tidak ada token terverifikasi yang layak jual** — trusted holdings = 0. Saldo native Ethereum nol. DAI di Sepolia (~30.0K) adalah token faucet testnet — tidak memiliki nilai ekonomi dunia nyata. RAIN di Arbitrum (~3.00) adalah token terverifikasi — nilai jual tidak dapat dikonfirmasi karena tidak ada data kedalaman pasar. **12 token spam diterima** — Dompet ini dibombardir oleh spam airdrop; jangan approve kontrak apa pun yang berasal dari token-token ini.

This is exactly the tone a serious analyst would write. It's not "AI summarizing data" — it's **investigator interpretation**.

## 5. Pitfalls Worth Documenting (for other MiMo builders)

These are real production findings from running MiMo at scale on Yarrr.Tech:

### 5.1 Reasoning tokens consume `max_tokens` BEFORE content

This is the single most important MiMo gotcha. If you set `max_tokens=500` and the prompt triggers complex reasoning, MiMo's internal reasoning eats the budget and `response.content` returns **empty** while `usage.completion_tokens` shows fully spent.

**Fix:** for analyst-style reports, use `max_tokens >= 1500`, ideally **4000**. We use 4000 in production.

```python
response = await mimo.chat.completions.create(
    model="mimo-v2.5",
    messages=[...],
    max_tokens=4000,  # not 500. not 1000. 4000.
)
```

### 5.2 Base URL is `api.xiaomimimo.com`, not `platform.xiaomimimo.com/openapi/v1`

Spent an hour debugging 404s before discovering the correct OpenAI-compat endpoint:

- ✅ `https://api.xiaomimimo.com/v1`
- ❌ `https://platform.xiaomimimo.com/openapi/v1`

Worth flagging in MiMo's docs more prominently.

### 5.3 Model variants

| Model | Use for |
|---|---|
| `mimo-v2.5` | Default reasoning. Yarrr.Tech production. |
| `mimo-v2.5-pro` | Deeper reasoning, longer latency. |
| `mimo-v2-flash` | Fast, lower-stakes tasks. |
| `mimo-v2-pro` | Pre-V2.5 generation. |
| `mimo-v2-omni` | Multimodal. |
| `mimo-v2.5-tts` | Text-to-speech. |

We default to `mimo-v2.5` and have not yet found a Yarrr.Tech use case that requires `pro`.

### 5.4 Rate limiting is generous

We have not hit MiMo rate limits in production. By contrast, Etherscan free-tier (5 RPS) is the actual bottleneck in our pipeline. This makes MiMo a non-issue from an ops perspective.

## 6. Performance — Real Numbers from Production

Measured over ~150 production analyses:

| Stage | P50 | P95 |
|---|---|---|
| Layer 1 (Etherscan multi-chain fetch, cold) | 38s | 51s |
| Layer 1 (cached partial) | 12s | 17s |
| Layer 2 (deterministic digest) | 80ms | 140ms |
| Layer 3 (MiMo V2.5 reasoning) | 6.2s | 11.4s |
| **Total user-facing latency (cold)** | **~48s** | **~62s** |
| **Total user-facing latency (warm)** | **~19s** | **~28s** |

MiMo is not the bottleneck. Etherscan's free-tier rate limit is. This means MiMo gives us *room to make Layers 1 + 2 faster* without becoming the new bottleneck — a healthy place to be.

Token usage per analysis:

| Tokens | Mean |
|---|---|
| Prompt input | ~1,800 |
| Reasoning (internal) | ~1,200 |
| Output content | ~2,400 |
| Total billed | ~5,400 |

## 7. What We Would Build with Expanded MiMo Access

If accepted into the Orbit 100T program, the additional token budget would directly unlock:

1. **Real-time wallet timeline view** — Layer 3 streams wallet history phase-by-phase (early activity → growth → dormancy → recovery) instead of single-shot analysis. Roughly 3-5x our current MiMo spend per wallet, gated today by cost.
2. **Sybil graph reasoning** — group multiple addresses, ask MiMo to reason about cluster behavior. Currently capped at 10 wallets per multi-analyze; with budget we'd extend to 50+ for serious sybil investigation.
3. **Composite reputation scoring** — quarterly automated re-analysis of tracked wallets to update their archetype + risk profile over time. Pure batch workload, perfect fit for MiMo cost profile.
4. **Pluggable provider abstract for non-EVM chains** — Solana, Sui, Aptos, Bitcoin. Each chain needs its own digest schema; MiMo handles the unifying analyst layer regardless of source.
5. **Public API for builders** — let other onchain tooling embed Yarrr.Tech wallet intel via API. Currently bottlenecked by our self-funded model spend.

## 8. Honest Limitations

We document failure modes openly:

- **Receive-only wallets** were initially scored "0 transactions" because `txlist` only returns outgoing. Fixed in v0.7 by adding `txlistinternal`, but it's a reminder that any onchain capture system has gaps.
- **Token "estimated value"** is calculated from net flow over a recent window, not from current `balanceOf` RPC calls. Net flow ≠ exact balance. We flag this caveat in the UI.
- **Unverified contracts** can be misclassified by symbol patterns. Our 7-level resolver mitigates this but doesn't eliminate it.
- **MiMo can still hedge** on truly ambiguous wallets — and that's the right behavior. Better to say "data is ambiguous" than fabricate a verdict.

These are honest engineering tradeoffs, not blockers.

## 9. Why This Application

Yarrr.Tech is not a hackathon demo. It's a real production system, live since April 2026, used by real users, building toward a clear north star: **the trustworthy AI investigator for onchain identity**.

MiMo is not bolted on for branding. It's load-bearing — the entire interpretation layer depends on its reasoning quality, Indonesian fluency, and cost profile. Replacing it with another model would force us to either degrade output quality or gate the feature behind a paywall.

The Orbit 100T program would directly enable the next phase of work documented in [PRODUCT.md](../PRODUCT.md): timeline streaming, sybil graph reasoning, public API. Token budget converts directly into shipped features for users.

## 10. Contact

- **Live site:** https://yarrr-node.com
- **Sample analysis:** https://yarrr-node.com/a/o7fwi2t5
- **GitHub:** github.com/AirdropLaura/yarrr-intel
- **Builder:** Bastiar — Telegram [@yarrr23](https://t.me/yarrr23)
- **Email:** (provided in application form)

---

<sub>Document version: 1.0 · Last updated: 2026-05-16 · Submitted as part of Xiaomi MiMo Orbit 100T application</sub>
