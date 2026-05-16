"""ENS / Basename resolution.

We use ENSIdeas' free public API for reverse resolution
(https://api.ensideas.com/ens/resolve/<addr>). Their endpoint:
- Handles ENS reverse + forward resolution
- Adds Coinbase Basenames support (Base mainnet)
- No API key required
- Returns {"name": "...", "displayName": "...", "avatar": "..."}

If the API fails, we silently fall back to None — the analyzer just shows the
raw 0x address. ENS is a nice-to-have, not a blocker.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

log = logging.getLogger("yarrr-tech.ens")

ENSIDEAS_API = "https://api.ensideas.com/ens/resolve"


async def resolve_name(address: str, client: httpx.AsyncClient | None = None) -> str | None:
    """Reverse-resolve an address to its ENS or Basename, whichever exists.

    Returns the human-readable name (e.g. `vitalik.eth`, `bastiar.base.eth`)
    or None if no record is set.
    """
    addr = address.lower()
    if not addr.startswith("0x") or len(addr) != 42:
        return None

    own_client = client is None
    client = client or httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=4.0))
    try:
        r = await client.get(f"{ENSIDEAS_API}/{addr}")
        if r.status_code != 200:
            return None
        data = r.json()
        # ENSIdeas returns {"address": "...", "name": "..."} when set, or
        # {"name": null} when the address has no ENS / Basename.
        name = data.get("name")
        if isinstance(name, str) and name:
            return name
        return None
    except Exception as e:
        log.debug("ENS resolve failed for %s: %s", address, e)
        return None
    finally:
        if own_client:
            await client.aclose()


async def resolve_name_safe(address: str) -> str | None:
    """Best-effort wrapper that swallows all exceptions and bounds latency."""
    try:
        return await asyncio.wait_for(resolve_name(address), timeout=6.0)
    except Exception as e:
        log.debug("ENS resolve failed for %s: %s", address, e)
        return None
