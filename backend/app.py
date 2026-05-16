"""FastAPI app — Yarrr.Tech wallet intelligence backend.

POST /api/analyze        — synchronous wallet analysis (returns full markdown)
POST /api/analyze/stream — Server-Sent Events stream of the same analysis
GET  /api/health         — liveness probe
GET  /api/resolve/{addr_or_name} — resolve ENS / Basename ↔ address (Phase 2)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from .archetypes import Archetype
from .chain import fetch_wallet_all_chains
from .ens import resolve_name_safe
from .intel import build_messages
from .mimo_client import MimoClient
from .persistence import get_snapshot, init_db, recent_for_address, save_snapshot
from .profiler import build_digest, digest_to_prompt_block, enrich_top_contracts

log = logging.getLogger("yarrr-tech")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")

ETH_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


class AnalyzeRequest(BaseModel):
    address: str = Field(..., description="EVM wallet address (0x...)")
    model: str = Field("mimo-v2.5", description="MiMo model id")
    lang: str = Field("id", description="Output language: 'id' (default) or 'en'")

    @field_validator("address")
    @classmethod
    def _valid(cls, v: str) -> str:
        v = v.strip()
        if not ETH_ADDRESS_RE.match(v):
            raise ValueError("must be a 0x-prefixed 40-hex-char EVM address")
        return v.lower()

    @field_validator("lang")
    @classmethod
    def _valid_lang(cls, v: str) -> str:
        v = (v or "").strip().lower()
        return v if v in {"id", "en"} else "en"


# ---------------------------------------------------------------------------
# In-memory cache for digests (raw on-chain data) — TTL 5 minutes.
# ---------------------------------------------------------------------------
_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 300.0  # 5 minutes


def _archetypes_to_dict(archetypes: list[Archetype]) -> list[dict]:
    return [
        {
            "name": a.name,
            "confidence": a.confidence,
            "bucket": a.bucket,
            "evidence": a.evidence,
        }
        for a in archetypes
    ]


async def _get_or_fetch_digest(address: str) -> dict:
    now = time.time()
    cached = _CACHE.get(address)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return cached[1]

    # Run ENS resolution + onchain fetch in parallel — both are network-bound
    # and independent, so doubling them up cuts latency by ~1-2s on average.
    name_task = asyncio.create_task(resolve_name_safe(address))
    chain_task = asyncio.create_task(fetch_wallet_all_chains(address))
    name = await name_task
    chain_data = await chain_task

    digest = build_digest(address, chain_data, name=name)
    # Phase 4 enrichment — replace "Unknown contract" labels with verified
    # names from token transfers, Etherscan getsourcecode, or selector hints.
    # Best-effort; never blocks digest delivery on failure.
    try:
        await enrich_top_contracts(digest, chain_data)
    except Exception as e:
        log.debug("enrich_top_contracts skipped: %s", e)
    block = digest_to_prompt_block(digest)
    payload = {
        "digest": {
            "address": digest.address,
            "name": digest.name,
            "chains_active": digest.chains_active,
            "chains_dormant": digest.chains_dormant,
            "mainnet_chains_active": digest.mainnet_chains_active,
            "testnet_chains_active": digest.testnet_chains_active,
            "balances_by_chain": digest.balances_by_chain,
            "txs_by_chain": digest.txs_by_chain,
            "total_txs": digest.total_txs,
            "total_internal_txs": digest.total_internal_txs,
            "partial_chains": digest.partial_chains,
            "total_balance_native": digest.total_balance_native,
            "error_rate": digest.error_rate,
            "first_tx_ts": digest.first_tx_ts,
            "last_tx_ts": digest.last_tx_ts,
            "days_active": digest.days_active,
            "days_since_last_tx": digest.days_since_last_tx,
            "wallet_age_days": digest.wallet_age_days,
            "activity_categories": digest.activity_categories,
            "top_contracts": digest.top_contracts,
            "recent_actions": digest.recent_actions,
            "funding_source": digest.funding_source,
            "funding_evidence": digest.funding_evidence,
            "tokens": {
                "stablecoin_volume_usd": digest.tokens.stablecoin_volume_usd,
                "stablecoin_chains": digest.tokens.stablecoin_chains,
                "distinct_stablecoins": digest.tokens.distinct_stablecoins,
                "distinct_erc20": digest.tokens.distinct_erc20,
                "holds_lp_tokens": digest.tokens.holds_lp_tokens,
                "holds_lst_tokens": digest.tokens.holds_lst_tokens,
                "distinct_nft_collections": digest.tokens.distinct_nft_collections,
                "spam_nft_count": digest.tokens.spam_nft_count,
                "spam_nft_examples": digest.tokens.spam_nft_examples,
                "holdings_trust": digest.tokens.holdings_trust,
                "holdings": [
                    {
                        "chain": h.chain,
                        "contract": h.contract,
                        "symbol": h.symbol,
                        "name": h.name,
                        "decimals": h.decimals,
                        "amount": h.amount,
                        "is_stablecoin": h.is_stablecoin,
                        "is_lp": h.is_lp,
                        "is_lst": h.is_lst,
                        "is_spam": h.is_spam,
                        "trust_tier": h.trust_tier,
                        "trust_score": h.trust_score,
                        "trust_summary": h.trust_summary,
                        "trust_reasons": h.trust_reasons,
                    }
                    for h in digest.tokens.holdings
                ],
            },
            "failed_tx_clusters": [
                {
                    "chain": fc.chain,
                    "target": fc.target,
                    "method": fc.method,
                    "count": fc.count,
                }
                for fc in digest.failed_tx_clusters
            ],
            "timeline": [
                {
                    "start_ts": tp.start_ts,
                    "end_ts": tp.end_ts,
                    "tx_count": tp.tx_count,
                    "chains": tp.chains,
                    "dominant_category": tp.dominant_category,
                    "error_rate": tp.error_rate,
                }
                for tp in digest.timeline
            ],
            "archetypes": _archetypes_to_dict(digest.archetypes),
            "reputation": (
                {
                    "score": digest.reputation.score,
                    "bucket": digest.reputation.bucket,
                    "raw_score": digest.reputation.raw_score,
                    "contributions": [
                        {"label": c.label, "delta": c.delta, "detail": c.detail}
                        for c in digest.reputation.contributions
                    ],
                }
                if digest.reputation
                else None
            ),
            "flags": digest.flags,
        },
        "prompt_block": block,
    }
    _CACHE[address] = (now, payload)
    if len(_CACHE) > 200:
        oldest = sorted(_CACHE.items(), key=lambda kv: kv[1][0])[:100]
        for k, _ in oldest:
            _CACHE.pop(k, None)
    return payload


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.mimo = MimoClient()
    init_db()
    from .cluster import init_funding_table
    from .contract_names import init_contract_names_table
    from .webhooks import init_webhook_table, start_watcher, stop_watcher
    init_funding_table()
    init_webhook_table()
    init_contract_names_table()
    app.state.webhook_task = start_watcher(app)
    log.info("MiMo client initialized · DB ready · funding+contract index ready · webhook watcher running")
    try:
        yield
    finally:
        await stop_watcher(app.state.webhook_task)
        await app.state.mimo.close()


app = FastAPI(
    title="Yarrr.Tech",
    description="AI-native onchain identity intelligence — paste any wallet, instantly understand what it actually does.",
    version="0.11.0",
    lifespan=lifespan,
)

allowed_origin = os.getenv("ALLOWED_ORIGIN", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[allowed_origin] if allowed_origin != "*" else ["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "service": "yarrr-tech", "version": app.version}


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest) -> dict:
    try:
        payload = await _get_or_fetch_digest(req.address)
    except Exception as e:
        log.exception("digest failed")
        raise HTTPException(status_code=502, detail=f"onchain fetch failed: {e}")

    messages = build_messages(payload["prompt_block"], lang=req.lang)
    try:
        result = await app.state.mimo.chat(messages=messages, model=req.model, max_tokens=4000)
    except Exception as e:
        log.exception("MiMo failed")
        raise HTTPException(status_code=502, detail=f"upstream error: {e}")

    return {
        "address": req.address,
        "content": result.content,
        "model": result.model,
        "usage": {
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "reasoning_tokens": result.reasoning_tokens,
            "total_tokens": result.total_tokens,
        },
        "latency_seconds": result.latency_seconds,
        "digest": payload["digest"],
    }


@app.post("/api/analyze/multi")
async def analyze_multi(payload: dict) -> dict:
    """Batch analyze 2-10 wallets in parallel.

    Body: {"addresses": ["0x…", "0x…"], "lang": "id" | "en", "model": "..."}
    Returns per-wallet digest + a side-by-side comparison block.

    LLM is called ONCE on the combined digests with a comparative-analyst
    prompt — much cheaper than N solo calls and produces sharper insight
    (the LLM can spot patterns across wallets).
    """
    addresses = payload.get("addresses") or []
    lang = (payload.get("lang") or "id").strip()
    model = payload.get("model") or "mimo-v2.5"

    # Validation
    if not isinstance(addresses, list) or not addresses:
        raise HTTPException(status_code=400, detail="addresses must be a non-empty list")
    if len(addresses) > 10:
        raise HTTPException(status_code=400, detail="max 10 addresses per batch")
    addresses = [a.strip() for a in addresses]
    for a in addresses:
        if not ETH_ADDRESS_RE.match(a):
            raise HTTPException(status_code=400, detail=f"invalid address: {a[:24]}…")
    # Dedupe while preserving order
    seen = set()
    unique = []
    for a in addresses:
        al = a.lower()
        if al not in seen:
            seen.add(al)
            unique.append(a)
    addresses = unique

    # Fetch digests in parallel — semaphore caps simultaneous chain scans
    sem = asyncio.Semaphore(3)

    async def one(addr: str):
        async with sem:
            try:
                return addr, await _get_or_fetch_digest(addr), None
            except Exception as e:
                log.exception("multi digest failed for %s", addr)
                return addr, None, str(e)

    results = await asyncio.gather(*[one(a) for a in addresses])

    # Build combined prompt block — concatenates each wallet's digest with a
    # "## Wallet N" delimiter so the LLM treats them as comparable entities.
    blocks: list[str] = []
    digests_out: list[dict] = []
    for i, (addr, p, err) in enumerate(results, 1):
        if err or not p:
            digests_out.append({"address": addr, "error": err or "unknown"})
            continue
        blocks.append(f"## Wallet {i}: {addr}\n\n{p['prompt_block']}")
        digests_out.append({"address": addr, **p["digest"]})

    if not blocks:
        raise HTTPException(status_code=502, detail="all digests failed")

    combined_prompt = "\n\n---\n\n".join(blocks)

    # Comparative analyst prompt — instruct LLM to look across wallets, not at
    # each one in isolation. Retry once on transient MiMo upstream errors.
    from .intel import build_messages_multi
    messages = build_messages_multi(combined_prompt, lang=lang, n=len(blocks))
    last_err = None
    for attempt in range(2):
        try:
            result = await app.state.mimo.chat(messages=messages, model=model, max_tokens=4000)
            break
        except Exception as e:
            last_err = e
            log.warning("MiMo multi-analyze attempt %d failed: %s", attempt + 1, e)
            if attempt == 0:
                await asyncio.sleep(2)
    else:
        log.exception("MiMo failed for multi-analyze after retries")
        raise HTTPException(status_code=502, detail=f"upstream error: {last_err}")

    return {
        "addresses": [d["address"] for d in digests_out],
        "content": result.content,
        "model": result.model,
        "usage": {
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "reasoning_tokens": result.reasoning_tokens,
            "total_tokens": result.total_tokens,
        },
        "latency_seconds": result.latency_seconds,
        "digests": digests_out,
    }


@app.post("/api/analyze/stream")
async def analyze_stream(req: AnalyzeRequest):
    async def generator():
        # Phase 1: fetch + digest
        yield f"data: {json.dumps({'phase': 'fetching', 'message': 'Scanning multichain footprint...'})}\n\n"
        try:
            payload = await _get_or_fetch_digest(req.address)
        except Exception as e:
            yield f"data: {json.dumps({'error': f'on-chain fetch failed: {e}'})}\n\n"
            return

        # Send digest summary for the UI to render the data panel
        yield f"data: {json.dumps({'phase': 'digest', 'digest': payload['digest']})}\n\n"

        # Phase 2: stream MiMo analysis
        yield f"data: {json.dumps({'phase': 'analyzing', 'message': 'Analyst is interpreting the wallet...'})}\n\n"
        messages = build_messages(payload["prompt_block"], lang=req.lang)
        try:
            async for chunk in app.state.mimo.chat_stream(messages=messages, model=req.model, max_tokens=4000):
                choice = (chunk.get("choices") or [{}])[0]
                delta = choice.get("delta") or {}
                if "content" in delta and delta["content"]:
                    yield f"data: {json.dumps({'delta': delta['content']})}\n\n"
                if choice.get("finish_reason"):
                    yield f"data: {json.dumps({'done': True, 'finish_reason': choice['finish_reason']})}\n\n"
        except Exception as e:
            log.exception("stream error")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/diagnose")
@app.post("/api/diagnose/stream")
async def deprecated_diagnose() -> dict:
    raise HTTPException(
        status_code=410,
        detail="The /api/diagnose endpoint has been removed. Yarrr.Tech is now a wallet intelligence engine — see /api/analyze.",
    )


# ---------------------------------------------------------------------------
# Share / persistence endpoints (Phase 2b)
# ---------------------------------------------------------------------------
class ShareRequest(BaseModel):
    address: str
    lang: str = "id"
    model: str = "mimo-v2.5"
    analysis: str               # markdown analyst output produced client-side

    @field_validator("address")
    @classmethod
    def _v(cls, v: str) -> str:
        v = v.strip().lower()
        if not ETH_ADDRESS_RE.match(v):
            raise ValueError("invalid EVM address")
        return v


@app.post("/api/share")
async def create_share(req: ShareRequest) -> dict:
    """Persist an analysis snapshot and return its share id.

    The frontend calls this after the streamed analyst output finishes. We
    snapshot the *current* digest from cache (or refetch if expired) plus the
    finalized markdown so the share URL renders the exact same view.
    """
    if not req.analysis.strip():
        raise HTTPException(status_code=400, detail="analysis content required")

    payload = await _get_or_fetch_digest(req.address)
    digest = payload["digest"]
    sid = save_snapshot(
        address=req.address,
        name=digest.get("name"),
        lang=req.lang,
        model=req.model,
        digest=digest,
        analysis=req.analysis,
    )
    return {"id": sid, "url": f"/a/{sid}"}


@app.get("/api/share/{sid}")
async def get_share_endpoint(sid: str) -> dict:
    """Retrieve a saved analysis by id."""
    snap = get_snapshot(sid)
    if not snap:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return {
        "id": snap.id,
        "address": snap.address,
        "name": snap.name,
        "lang": snap.lang,
        "model": snap.model,
        "digest": snap.digest,
        "content": snap.analysis,
        "created_at": snap.created_at,
    }


@app.get("/api/og/{sid}.png")
async def get_og_image(sid: str):
    """Generate (or serve cached) OG card PNG for a shared analysis.

    Cached for 1h on the client; backend regenerates from snapshot data each
    time the cache misses. ~80ms per render so we don't bother persisting the
    bytes — keeps the share table small.
    """
    from .og_image import render_og_png

    snap = get_snapshot(sid)
    if not snap:
        raise HTTPException(404, detail="snapshot not found")

    digest = snap.digest or {}
    try:
        png = render_og_png(
            address=snap.address,
            name=snap.name,
            archetypes=digest.get("archetypes") or [],
            total_txs=int(digest.get("total_txs") or 0),
            mainnet_count=len(digest.get("mainnet_chains_active") or []),
            testnet_count=len(digest.get("testnet_chains_active") or []),
            reputation=digest.get("reputation"),
        )
    except Exception as e:
        log.exception("og render failed for %s: %s", sid, e)
        raise HTTPException(500, detail="og render failed")

    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/a/{sid}", response_class=HTMLResponse)
@app.get("/a/{sid}/", response_class=HTMLResponse)
async def serve_share_html(sid: str):
    """Server-rendered HTML for `/a/<id>/` so social crawlers see real OG meta.

    Browsers (Telegram preview bot, Twitter card scraper, Discord) don't
    execute JavaScript — they just GET the URL and parse `<meta>` tags. We
    inject the snapshot-specific meta server-side, then redirect users via
    `<meta refresh>` to the SPA at `/a/?sid=<id>` for interactive rendering.
    Crawlers stop at the meta tags and grab the OG image.
    """
    import html as _html

    snap = get_snapshot(sid)
    if not snap:
        return HTMLResponse(
            content=(
                f"<html><head><title>Yarrr.Tech · Not Found</title>"
                f"<meta http-equiv=\"refresh\" content=\"0;url=/a/?sid={_html.escape(sid)}\"/>"
                f"</head><body>Loading…</body></html>"
            ),
            status_code=404,
        )

    digest = snap.digest or {}
    archetypes = digest.get("archetypes") or []
    primary_arche = archetypes[0]["name"] if archetypes else None
    name = snap.name or (snap.address[:8] + "…" + snap.address[-4:])
    mainnets = len(digest.get("mainnet_chains_active") or [])
    total_tx = digest.get("total_txs", 0)

    title = f"{name} · Yarrr.Tech"
    if primary_arche:
        desc = f"Onchain identity: {primary_arche}. {mainnets} mainnets · {total_tx} tx."
    else:
        desc = f"Wallet intelligence on {mainnets} mainnets · {total_tx} tx."

    canonical = f"https://yarrr-node.com/a/{sid}/"
    og_image = f"https://yarrr-node.com/api/og/{sid}.png"

    title_e = _html.escape(title)
    desc_e = _html.escape(desc)
    sid_e = _html.escape(sid)
    lang_e = _html.escape(snap.lang or "en")

    body = f"""<!DOCTYPE html>
<html lang="{lang_e}">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title_e}</title>
<meta name="description" content="{desc_e}"/>
<link rel="canonical" href="{canonical}"/>

<meta property="og:type" content="website"/>
<meta property="og:site_name" content="Yarrr.Tech"/>
<meta property="og:title" content="{title_e}"/>
<meta property="og:description" content="{desc_e}"/>
<meta property="og:url" content="{canonical}"/>
<meta property="og:image" content="{og_image}"/>
<meta property="og:image:width" content="1200"/>
<meta property="og:image:height" content="630"/>

<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:title" content="{title_e}"/>
<meta name="twitter:description" content="{desc_e}"/>
<meta name="twitter:image" content="{og_image}"/>

<meta http-equiv="refresh" content="0; url=/a/?sid={sid_e}"/>
<style>body{{background:#0a0b10;color:#f0f2fa;font-family:monospace;margin:0;padding:24px}}</style>
</head>
<body>
<p>Loading shared analysis <b>{sid_e}</b>…</p>
<p>If you are not redirected, <a href="/a/?sid={sid_e}" style="color:#fbbf24">click here</a>.</p>
</body>
</html>
"""
    return HTMLResponse(content=body, status_code=200)


@app.post("/api/webhooks")
async def webhook_subscribe(payload: dict) -> dict:
    """Subscribe to wallet activity changes.

    Body: {"address": "0x…", "webhook_url": "https://…", "lang": "en"}
    Returns: subscription id + event types we'll send.

    Idempotent on (address, webhook_url) — same body returns existing sub.
    """
    from .webhooks import create_subscription

    address = (payload.get("address") or "").strip()
    url = (payload.get("webhook_url") or "").strip()
    lang = (payload.get("lang") or "en").strip()

    if not ETH_ADDRESS_RE.match(address):
        raise HTTPException(status_code=400, detail="invalid address")
    if not (url.startswith("https://") or url.startswith("http://")):
        raise HTTPException(status_code=400, detail="webhook_url must be http(s)")
    if len(url) > 1000:
        raise HTTPException(status_code=400, detail="webhook_url too long")

    sub = create_subscription(address, url, lang)
    return {
        "id": sub.id,
        "address": sub.address,
        "webhook_url": sub.webhook_url,
        "created_at": sub.created_at,
        "event_types": [
            "archetype_change",
            "reputation_rise",
            "reputation_drop",
            "wake_from_dormancy",
            "new_chain",
        ],
        "poll_interval_minutes": 15,
    }


@app.get("/api/webhooks")
async def webhook_list(address: str | None = None) -> dict:
    """List subscriptions, optionally filtered by address."""
    from .webhooks import list_subscriptions

    subs = list_subscriptions(address)
    return {
        "count": len(subs),
        "subscriptions": [
            {
                "id": s.id,
                "address": s.address,
                "webhook_url": s.webhook_url,
                "created_at": s.created_at,
                "last_check": s.last_check,
                "fail_count": s.fail_count,
                "paused": s.paused,
            }
            for s in subs
        ],
    }


@app.delete("/api/webhooks/{sub_id}")
async def webhook_delete(sub_id: str) -> dict:
    from .webhooks import delete_subscription

    ok = delete_subscription(sub_id)
    if not ok:
        raise HTTPException(status_code=404, detail="subscription not found")
    return {"deleted": sub_id}


@app.get("/api/cluster/{address}")
async def get_cluster(address: str) -> dict:
    """Sybil graph: wallets that share funding events with `address`.

    Returns matches only when MIN_CLUSTER_SIZE+ siblings are found. Empty
    response when the database doesn't yet have enough data — the cluster
    panel hides itself client-side.
    """
    from .cluster import MIN_CLUSTER_SIZE, find_cluster

    address = address.strip()
    if not ETH_ADDRESS_RE.match(address):
        raise HTTPException(status_code=400, detail="invalid address")

    report = find_cluster(address)
    has_cluster = report.distinct_wallets >= MIN_CLUSTER_SIZE
    return {
        "address": report.address,
        "has_cluster": has_cluster,
        "distinct_wallets": report.distinct_wallets,
        "distinct_sources": report.distinct_sources,
        "matches": [
            {
                "wallet": m.wallet,
                "source_addr": m.source_addr,
                "source_type": m.source_type,
                "chain": m.chain,
                "ts": m.ts,
                "delta_seconds": m.delta_seconds,
            }
            for m in report.matches[:25]   # cap response size
        ],
    }


@app.get("/api/history/{address}")
async def get_history(address: str) -> dict:
    """Recent shared analyses for a wallet (lightweight)."""
    if not ETH_ADDRESS_RE.match(address.strip()):
        raise HTTPException(status_code=400, detail="invalid address")
    return {"address": address.lower(), "snapshots": recent_for_address(address)}
