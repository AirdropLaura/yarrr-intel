"""SQLite-backed persistence for shareable analysis snapshots.

Why SQLite + a single file:
- We're on one VPS. No need for Postgres or external DB.
- Analyses are immutable snapshots. Heavy reads, rare writes. SQLite handles
  thousands of req/s on a small box without breaking a sweat.
- Single file backup = `cp yarrr.db yarrr.db.bak`. Recovery is trivial.

Schema:
    snapshots(
        id          TEXT PRIMARY KEY,    -- 8-char shortid (base32)
        address     TEXT NOT NULL,        -- 0x... lowercased
        name        TEXT,                 -- ENS / Basename if any
        lang        TEXT NOT NULL,        -- 'id' | 'en'
        model       TEXT NOT NULL,        -- mimo-v2.5 etc.
        digest      TEXT NOT NULL,        -- JSON-encoded digest payload
        analysis    TEXT NOT NULL,        -- analyst markdown output
        created_at  INTEGER NOT NULL      -- unix seconds
    )
    INDEX snapshots_address_idx ON snapshots(address, created_at DESC)

The id is generated from a hash of (address, lang, digest+analysis content).
Same input → same id, so re-sharing the same analysis is idempotent.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass

DB_PATH = os.path.expanduser(os.getenv("YARRR_DB_PATH", "/opt/yarrr-intel/yarrr.db"))

# SQLite is mostly thread-safe in serialized mode, but we still wrap writes in
# a lock to avoid contention surprises with FastAPI's threadpool fallback.
_WRITE_LOCK = threading.Lock()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def init_db() -> None:
    """Create the snapshots table if it doesn't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id          TEXT PRIMARY KEY,
                address     TEXT NOT NULL,
                name        TEXT,
                lang        TEXT NOT NULL,
                model       TEXT NOT NULL,
                digest      TEXT NOT NULL,
                analysis    TEXT NOT NULL,
                created_at  INTEGER NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS snapshots_address_idx ON snapshots(address, created_at DESC)")
        conn.commit()


@contextmanager
def _cursor():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


@dataclass
class Snapshot:
    id: str
    address: str
    name: str | None
    lang: str
    model: str
    digest: dict
    analysis: str
    created_at: int


def _generate_id(address: str, lang: str, digest_json: str, analysis: str) -> str:
    """Deterministic 8-char id from content hash. Base32 alphabet (no padding)
    drops to lowercase for cleaner URLs. Collisions astronomically unlikely
    (40 bits = 1 in a trillion before 50% birthday chance)."""
    h = hashlib.sha256()
    h.update(address.encode())
    h.update(b"|" + lang.encode())
    h.update(b"|" + digest_json.encode())
    h.update(b"|" + analysis.encode())
    raw = h.digest()
    # base32 → 8 chars from first 5 bytes (40 bits)
    return base64.b32encode(raw[:5]).decode().lower().rstrip("=")


def save_snapshot(
    *,
    address: str,
    name: str | None,
    lang: str,
    model: str,
    digest: dict,
    analysis: str,
) -> str:
    """Persist an analysis snapshot. Returns the share id."""
    digest_json = json.dumps(digest, sort_keys=True, separators=(",", ":"))
    sid = _generate_id(address, lang, digest_json, analysis)

    with _WRITE_LOCK, _cursor() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO snapshots
                (id, address, name, lang, model, digest, analysis, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (sid, address.lower(), name, lang, model, digest_json, analysis, int(time.time())),
        )
    return sid


def get_snapshot(sid: str) -> Snapshot | None:
    """Retrieve a snapshot by id. Returns None if not found."""
    with _cursor() as conn:
        row = conn.execute("SELECT * FROM snapshots WHERE id = ?", (sid,)).fetchone()
    if not row:
        return None
    try:
        digest = json.loads(row["digest"])
    except (TypeError, ValueError):
        digest = {}
    return Snapshot(
        id=row["id"],
        address=row["address"],
        name=row["name"],
        lang=row["lang"],
        model=row["model"],
        digest=digest,
        analysis=row["analysis"],
        created_at=row["created_at"],
    )


def recent_for_address(address: str, limit: int = 5) -> list[dict]:
    """Lightweight history listing for a wallet (used by /api/history/{addr})."""
    with _cursor() as conn:
        rows = conn.execute(
            """
            SELECT id, lang, model, created_at
            FROM snapshots
            WHERE address = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (address.lower(), limit),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "lang": r["lang"],
            "model": r["model"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
