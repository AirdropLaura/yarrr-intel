"""FastAPI app — Yarrr.Intel wallet intelligence backend.

POST /api/analyze        — synchronous wallet analysis (returns full markdown)
POST /api/analyze/stream — Server-Sent Events stream of the same analysis
GET  /api/health         — liveness probe
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from .chain import fetch_wallet_all_chains
from .intel import build_messages
from .mimo_client import MimoClient
from .profiler import build_digest, digest_to_prompt_block

log = logging.getLogger("yarrr-intel")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")

ETH_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


class AnalyzeRequest(BaseModel):
    address: str = Field(..., description="EVM wallet address (0x...)")
    model: str = Field("mimo-v2.5", description="MiMo model id")

    @field_validator("address")
    @classmethod
    def _valid(cls, v: str) -> str:
        v = v.strip()
        if not ETH_ADDRESS_RE.match(v):
            raise ValueError("must be a 0x-prefixed 40-hex-char EVM address")
        return v.lower()


# ---------------------------------------------------------------------------
# In-memory cache for digests (raw on-chain data) — TTL 5 minutes.
# Avoids hammering Etherscan/Blockscout if the user retries or shares a URL.
# ---------------------------------------------------------------------------
_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 300.0  # 5 minutes


async def _get_or_fetch_digest(address: str) -> dict:
    now = time.time()
    cached = _CACHE.get(address)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return cached[1]
    chain_data = await fetch_wallet_all_chains(address)
    digest = build_digest(address, chain_data)
    block = digest_to_prompt_block(digest)
    payload = {
        "digest": {
            "address": digest.address,
            "chains_active": digest.chains_active,
            "chains_dormant": digest.chains_dormant,
            "balances_by_chain": digest.balances_by_chain,
            "txs_by_chain": digest.txs_by_chain,
            "total_txs": digest.total_txs,
            "error_rate": digest.error_rate,
            "first_tx_ts": digest.first_tx_ts,
            "last_tx_ts": digest.last_tx_ts,
            "days_active": digest.days_active,
            "days_since_last_tx": digest.days_since_last_tx,
            "activity_categories": digest.activity_categories,
            "top_contracts": digest.top_contracts,
            "recent_actions": digest.recent_actions,
            "flags": digest.flags,
        },
        "prompt_block": block,
    }
    _CACHE[address] = (now, payload)
    # Soft size cap.
    if len(_CACHE) > 200:
        oldest = sorted(_CACHE.items(), key=lambda kv: kv[1][0])[:100]
        for k, _ in oldest:
            _CACHE.pop(k, None)
    return payload


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.mimo = MimoClient()
    log.info("MiMo client initialized")
    yield
    await app.state.mimo.close()


app = FastAPI(
    title="Yarrr.Intel",
    description="AI Wallet Intelligence — paste any wallet, instantly understand what it does.",
    version="0.3.0",
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
    return {"ok": True, "service": "yarrr-intel", "version": app.version}


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest) -> dict:
    try:
        payload = await _get_or_fetch_digest(req.address)
    except Exception as e:
        log.exception("digest failed")
        raise HTTPException(status_code=502, detail=f"onchain fetch failed: {e}")

    messages = build_messages(payload["prompt_block"])
    try:
        result = await app.state.mimo.chat(messages=messages, model=req.model, max_tokens=2500)
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


@app.post("/api/analyze/stream")
async def analyze_stream(req: AnalyzeRequest):
    async def generator():
        # Phase 1: fetch + digest
        yield f"data: {json.dumps({'phase': 'fetching', 'message': 'Scanning 5 chains...'})}\n\n"
        try:
            payload = await _get_or_fetch_digest(req.address)
        except Exception as e:
            yield f"data: {json.dumps({'error': f'on-chain fetch failed: {e}'})}\n\n"
            return

        # Send digest summary for the UI to render the data panel
        yield f"data: {json.dumps({'phase': 'digest', 'digest': payload['digest']})}\n\n"

        # Phase 2: stream MiMo analysis
        yield f"data: {json.dumps({'phase': 'analyzing', 'message': 'AI is interpreting the wallet...'})}\n\n"
        messages = build_messages(payload["prompt_block"])
        try:
            async for chunk in app.state.mimo.chat_stream(messages=messages, model=req.model, max_tokens=2500):
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


# Keep the old diagnostic endpoint optionally? No — full pivot.
# This signals the change clearly to anyone hitting old endpoints.
@app.post("/api/diagnose")
@app.post("/api/diagnose/stream")
async def deprecated_diagnose() -> dict:
    raise HTTPException(
        status_code=410,
        detail="The /api/diagnose endpoint has been removed. Yarrr has pivoted to wallet intelligence — see /api/analyze.",
    )
