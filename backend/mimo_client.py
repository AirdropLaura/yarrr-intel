"""MiMo API client wrapper.

Thin abstraction over Xiaomi MiMo's OpenAI-compatible chat endpoint. Handles
auth, retries, streaming, and reasoning-token accounting.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import AsyncIterator

import httpx

MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"


def _load_api_key() -> str:
    # 1) env var (highest priority for prod / docker)
    key = os.getenv("MIMO_API_KEY")
    if key:
        return key
    # 2) credential file (dev / VPS direct)
    cred_path = os.path.expanduser("~/.hermes/credentials/mimo.env")
    if os.path.exists(cred_path):
        for line in open(cred_path):
            line = line.strip()
            if line.startswith("MIMO_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("MIMO_API_KEY not set and ~/.hermes/credentials/mimo.env missing")


@dataclass
class ChatResult:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    total_tokens: int
    latency_seconds: float


class MimoClient:
    def __init__(self, api_key: str | None = None, base_url: str = MIMO_BASE_URL):
        self.api_key = api_key or _load_api_key()
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(120.0, connect=10.0),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

    async def chat(
        self,
        messages: list[dict],
        model: str = "mimo-v2.5",
        max_tokens: int = 2000,
        temperature: float = 0.3,
    ) -> ChatResult:
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        t0 = time.time()
        resp = await self._client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage", {}) or {}
        details = usage.get("completion_tokens_details", {}) or {}
        return ChatResult(
            content=data["choices"][0]["message"]["content"] or "",
            model=data.get("model", model),
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            reasoning_tokens=int(details.get("reasoning_tokens", 0)),
            total_tokens=int(usage.get("total_tokens", 0)),
            latency_seconds=round(time.time() - t0, 2),
        )

    async def chat_stream(
        self,
        messages: list[dict],
        model: str = "mimo-v2.5",
        max_tokens: int = 2000,
        temperature: float = 0.3,
    ) -> AsyncIterator[dict]:
        """Yield SSE chunks. Each chunk is a parsed JSON dict from the stream."""
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        async with self._client.stream("POST", "/chat/completions", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    yield json.loads(data)
                except json.JSONDecodeError:
                    continue

    async def close(self) -> None:
        await self._client.aclose()
