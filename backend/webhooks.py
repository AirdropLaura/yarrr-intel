"""Webhook subscriptions — Phase 3.6.

Lets users subscribe to a wallet and receive HTTP POST notifications when
something interesting changes. Designed to be gentle on resources:

- Single SQLite table `webhook_subscriptions`
- One async background loop polls every WATCH_INTERVAL seconds
- For each subscription, re-runs the analyzer and diffs against the last
  recorded snapshot (archetype set, reputation bucket, dormancy state)
- POSTs a compact JSON payload to the user's URL on change

Trigger types we surface:
- archetype_change   — primary archetype flipped to a different name
- reputation_drop    — bucket dropped one or more tiers
- reputation_rise    — bucket rose one or more tiers
- wake_from_dormancy — wallet was dormant (>180d), now active
- new_chain          — wallet appeared on a chain it hadn't touched before

Idempotency: a subscription has a `last_state` JSON blob; we only fire when
the new state differs. Failed POSTs increment `fail_count`; subscriptions
auto-pause after MAX_FAILS to prevent runaway retries.

Privacy: webhook URL is stored verbatim. We don't sign payloads (no shared
secret on creation flow yet); users should treat the URL as the secret.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import secrets
import time
from dataclasses import dataclass

import httpx

from .persistence import _connect

log = logging.getLogger("yarrr-tech.webhooks")

# How often to poll (in seconds). 15 minutes feels fine for free-tier
# Etherscan budget; subscribers can't exceed this regardless of urgency.
WATCH_INTERVAL = 15 * 60

# Time to wait between processing each subscription, to spread API load.
PER_SUB_DELAY = 4

# Pause subscription after this many consecutive POST failures.
MAX_FAILS = 5

# Reputation bucket ordering for diff comparisons.
_BUCKET_ORDER = {"poor": 0, "low": 1, "neutral": 2, "good": 3, "high": 4}

# Dormancy threshold matches archetype detection.
DORMANT_DAYS = 180


def init_webhook_table() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS webhook_subscriptions (
                id          TEXT PRIMARY KEY,
                address     TEXT NOT NULL,
                webhook_url TEXT NOT NULL,
                created_at  INTEGER NOT NULL,
                last_check  INTEGER,
                last_state  TEXT,
                fail_count  INTEGER NOT NULL DEFAULT 0,
                paused      INTEGER NOT NULL DEFAULT 0,
                lang        TEXT DEFAULT 'en',
                UNIQUE(address, webhook_url)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_webhook_addr ON webhook_subscriptions(address)"
        )
        conn.commit()


@dataclass
class Subscription:
    id: str
    address: str
    webhook_url: str
    created_at: int
    last_check: int | None
    last_state: dict | None
    fail_count: int
    paused: bool
    lang: str


def _row_to_sub(r) -> Subscription:
    state = None
    if r["last_state"]:
        try:
            state = json.loads(r["last_state"])
        except (TypeError, ValueError):
            state = None
    return Subscription(
        id=r["id"],
        address=r["address"],
        webhook_url=r["webhook_url"],
        created_at=int(r["created_at"]),
        last_check=int(r["last_check"]) if r["last_check"] is not None else None,
        last_state=state,
        fail_count=int(r["fail_count"]),
        paused=bool(r["paused"]),
        lang=r["lang"] or "en",
    )


def create_subscription(address: str, webhook_url: str, lang: str = "en") -> Subscription:
    """Idempotent — same (address, webhook_url) returns existing row."""
    sub_id = secrets.token_urlsafe(12)
    now = int(time.time())
    with _connect() as conn:
        try:
            conn.execute(
                """
                INSERT INTO webhook_subscriptions (id, address, webhook_url, created_at, lang)
                VALUES (?, ?, ?, ?, ?)
                """,
                (sub_id, address.lower(), webhook_url, now, lang),
            )
            conn.commit()
        except Exception:
            # UNIQUE collision — pull existing
            pass
        row = conn.execute(
            "SELECT * FROM webhook_subscriptions WHERE address = ? AND webhook_url = ?",
            (address.lower(), webhook_url),
        ).fetchone()
        return _row_to_sub(row)


def list_subscriptions(address: str | None = None) -> list[Subscription]:
    with _connect() as conn:
        if address:
            rows = conn.execute(
                "SELECT * FROM webhook_subscriptions WHERE address = ? ORDER BY created_at DESC",
                (address.lower(),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM webhook_subscriptions WHERE paused = 0 ORDER BY last_check ASC NULLS FIRST"
            ).fetchall()
        return [_row_to_sub(r) for r in rows]


def delete_subscription(sub_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM webhook_subscriptions WHERE id = ?", (sub_id,))
        conn.commit()
        return cur.rowcount > 0


def _record_check(sub_id: str, state: dict, fail_count: int = 0, pause: bool = False) -> None:
    with _connect() as conn:
        conn.execute(
            """
            UPDATE webhook_subscriptions
            SET last_check = ?, last_state = ?, fail_count = ?, paused = ?
            WHERE id = ?
            """,
            (int(time.time()), json.dumps(state), fail_count, 1 if pause else 0, sub_id),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Diff logic
# ---------------------------------------------------------------------------

def _digest_to_state(digest: dict) -> dict:
    """Reduce a digest down to the fields we diff against."""
    archetypes = digest.get("archetypes") or []
    primary = archetypes[0]["name"] if archetypes else None
    rep = digest.get("reputation") or {}
    return {
        "primary_archetype": primary,
        "archetype_set": sorted(a["name"] for a in archetypes),
        "reputation_bucket": rep.get("bucket"),
        "reputation_score": rep.get("score"),
        "active_chains": sorted(c["chain"] for c in (digest.get("chains") or []) if c.get("tx_count")),
        "wallet_age_days": digest.get("wallet_age_days"),
        "days_since_last_tx": digest.get("days_since_last_tx"),
    }


def _diff(prev: dict | None, cur: dict) -> list[dict]:
    """Return list of trigger events; empty list = nothing notable."""
    if prev is None:
        return []   # First run — establish baseline silently.

    events: list[dict] = []

    # Archetype flip
    p_arch = prev.get("primary_archetype")
    c_arch = cur.get("primary_archetype")
    if p_arch and c_arch and p_arch != c_arch:
        events.append({
            "type": "archetype_change",
            "from": p_arch,
            "to": c_arch,
        })

    # Reputation tier change
    p_b = prev.get("reputation_bucket")
    c_b = cur.get("reputation_bucket")
    if p_b in _BUCKET_ORDER and c_b in _BUCKET_ORDER and p_b != c_b:
        if _BUCKET_ORDER[c_b] > _BUCKET_ORDER[p_b]:
            events.append({
                "type": "reputation_rise",
                "from": p_b, "to": c_b,
                "score": cur.get("reputation_score"),
            })
        else:
            events.append({
                "type": "reputation_drop",
                "from": p_b, "to": c_b,
                "score": cur.get("reputation_score"),
            })

    # Dormancy → active
    p_dorm = (prev.get("days_since_last_tx") or 0) >= DORMANT_DAYS
    c_dorm = (cur.get("days_since_last_tx") or 0) >= DORMANT_DAYS
    if p_dorm and not c_dorm:
        events.append({
            "type": "wake_from_dormancy",
            "previous_idle_days": prev.get("days_since_last_tx"),
        })

    # New chain footprint
    p_chains = set(prev.get("active_chains") or [])
    c_chains = set(cur.get("active_chains") or [])
    new_chains = c_chains - p_chains
    if new_chains:
        events.append({
            "type": "new_chain",
            "chains": sorted(new_chains),
        })

    return events


# ---------------------------------------------------------------------------
# Background watcher loop
# ---------------------------------------------------------------------------

async def _post_webhook(sub: Subscription, payload: dict, client: httpx.AsyncClient) -> bool:
    try:
        r = await client.post(sub.webhook_url, json=payload, timeout=8)
        return 200 <= r.status_code < 300
    except Exception as e:
        log.debug("webhook POST failed for %s: %s", sub.id, e)
        return False


async def _check_one(sub: Subscription, app, client: httpx.AsyncClient) -> None:
    """Re-analyze the wallet, diff state, fire webhook if events accumulated."""
    from .chain import fetch_wallet_all_chains
    from .ens import resolve_name
    from .profiler import build_digest

    try:
        chains_data = await fetch_wallet_all_chains(sub.address)
        name = await resolve_name(sub.address, client=client)
        digest = build_digest(sub.address, chains_data, name=name)
        state = _digest_to_state({
            "archetypes": [{"name": a.name} for a in digest.archetypes],
            "reputation": (
                {"bucket": digest.reputation.bucket, "score": digest.reputation.score}
                if digest.reputation else {}
            ),
            "chains": [
                {"chain": c.chain, "tx_count": c.tx_count}
                for c in chains_data
            ],
            "wallet_age_days": digest.wallet_age_days,
            "days_since_last_tx": digest.days_since_last_tx,
        })
    except Exception as e:
        log.warning("subscription %s: re-analyze failed: %s", sub.id, e)
        _record_check(sub.id, sub.last_state or {}, sub.fail_count + 1,
                      pause=(sub.fail_count + 1 >= MAX_FAILS))
        return

    events = _diff(sub.last_state, state)
    if not events:
        _record_check(sub.id, state, fail_count=0)
        return

    payload = {
        "subscription_id": sub.id,
        "address": sub.address,
        "events": events,
        "snapshot": state,
        "checked_at": int(time.time()),
    }
    ok = await _post_webhook(sub, payload, client)
    if ok:
        _record_check(sub.id, state, fail_count=0)
        log.info("subscription %s: %d events delivered", sub.id, len(events))
    else:
        new_fails = sub.fail_count + 1
        pause = new_fails >= MAX_FAILS
        _record_check(sub.id, state, fail_count=new_fails, pause=pause)
        if pause:
            log.warning("subscription %s auto-paused after %d failures", sub.id, MAX_FAILS)


async def watcher_loop(app) -> None:
    """Long-running task. Sleeps between rounds. Cancels gracefully."""
    log.info("webhook watcher loop started, interval=%ds", WATCH_INTERVAL)
    async with httpx.AsyncClient() as client:
        while True:
            try:
                subs = list_subscriptions()
                if subs:
                    log.debug("watcher round: %d active subs", len(subs))
                for sub in subs:
                    if sub.paused:
                        continue
                    try:
                        await _check_one(sub, app, client)
                    except Exception as e:
                        log.exception("watcher: error checking %s: %s", sub.id, e)
                    await asyncio.sleep(PER_SUB_DELAY)
            except asyncio.CancelledError:
                log.info("webhook watcher loop cancelled")
                raise
            except Exception as e:
                log.exception("watcher loop error: %s", e)
            try:
                await asyncio.sleep(WATCH_INTERVAL)
            except asyncio.CancelledError:
                raise


def start_watcher(app) -> asyncio.Task:
    task = asyncio.create_task(watcher_loop(app))
    return task


async def stop_watcher(task: asyncio.Task) -> None:
    if task and not task.done():
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
