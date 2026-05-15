"""FastAPI app — Yarrr.Tech diagnostic backend.

POST /api/diagnose — synchronous diagnosis (returns full markdown).
POST /api/diagnose/stream — Server-Sent Events stream of the same diagnosis.
GET  /api/health — liveness probe.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .diagnose import build_diagnosis_messages
from .mimo_client import MimoClient

log = logging.getLogger("yarrr-tech")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")


class DiagnoseRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000, description="Log, error, or config snippet")
    network: str | None = Field(None, max_length=80)
    os_name: str | None = Field(None, max_length=80)
    context: str | None = Field(None, max_length=2000)
    model: str = Field("mimo-v2.5", description="MiMo model id")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.mimo = MimoClient()
    log.info("MiMo client initialized")
    yield
    await app.state.mimo.close()


app = FastAPI(
    title="Yarrr.Tech",
    description="AI-native diagnostics for testnet & validator node operators",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — open during dev. Tighten to actual origin in prod via env var.
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


@app.post("/api/diagnose")
async def diagnose(req: DiagnoseRequest) -> dict:
    messages = build_diagnosis_messages(req.text, req.network, req.os_name, req.context)
    try:
        result = await app.state.mimo.chat(messages=messages, model=req.model, max_tokens=2500)
    except Exception as e:
        log.exception("MiMo call failed")
        raise HTTPException(status_code=502, detail=f"upstream error: {e}")
    return {
        "content": result.content,
        "model": result.model,
        "usage": {
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "reasoning_tokens": result.reasoning_tokens,
            "total_tokens": result.total_tokens,
        },
        "latency_seconds": result.latency_seconds,
    }


@app.post("/api/diagnose/stream")
async def diagnose_stream(req: DiagnoseRequest):
    messages = build_diagnosis_messages(req.text, req.network, req.os_name, req.context)

    async def generator():
        try:
            async for chunk in app.state.mimo.chat_stream(messages=messages, model=req.model, max_tokens=2500):
                # Forward only what the client needs.
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
