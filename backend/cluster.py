"""Sybil graph — Layer 2.6.

Detects wallets that look like they belong to the same operator by clustering
on shared funding events. Strategy:

- Every time `/api/analyze` runs, we extract the wallet's *earliest* inbound
  funding event(s) — typically the very first non-zero ETH it ever received.
- We index that event in `wallet_funding` keyed by source address + chain +
  ts. Idempotent on (wallet, source, ts).
- Cluster query: "find every other wallet we have on file that received
  funds from the SAME source on the SAME chain within ±15 minutes." That's
  the canonical sybil signal — one operator splitting funding to N wallets
  from a CEX hot wallet or bridge contract in rapid succession.

Privacy note: only earliest funding events are stored. We do not log every
inbound transfer the wallet ever received. The data here is public on-chain
information; we're just indexing for fast reverse-lookup.

Limits we accept:
- Empty database at first — clusters only emerge after enough wallets have
  been analyzed. That's intentional — coverage compounds with usage.
- 15-minute window is a heuristic. Most sybil farming bots split funding
  over 60-300 seconds; 15min gives enough slack for human-paced operators
  without false-positive matches across unrelated days.
- We don't infer relations from bridge events alone — bridges are public
  highways, anyone can use them. CEX hot wallet origins are the high-signal
  cluster markers.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass

from .persistence import _connect

log = logging.getLogger("yarrr-tech.cluster")

# Widow for "same funding event" — 15 minutes either side.
CLUSTER_WINDOW_SEC = 15 * 60

# Minimum cluster size to surface in the API. Single-match clusters are noise
# (one other wallet happened to be funded near the same time); we want at
# least 2 siblings to call it a cluster.
MIN_CLUSTER_SIZE = 2


def init_funding_table() -> None:
    """Create the wallet_funding table if it doesn't exist."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS wallet_funding (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet TEXT NOT NULL,
                source_addr TEXT NOT NULL,
                source_type TEXT NOT NULL,    -- cex / bridge / airdrop / unknown
                chain TEXT NOT NULL,
                tx_hash TEXT,
                ts INTEGER NOT NULL,
                value_eth REAL,
                recorded_at INTEGER NOT NULL,
                UNIQUE(wallet, source_addr, ts)
            )
            """
        )
        # Index for the cluster query — by source + ts, the hot path.
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_funding_source_ts
            ON wallet_funding(source_addr, chain, ts)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_funding_wallet
            ON wallet_funding(wallet)
            """
        )
        conn.commit()


@dataclass
class FundingEvent:
    wallet: str
    source_addr: str
    source_type: str        # cex / bridge / airdrop / unknown
    chain: str
    ts: int
    tx_hash: str | None = None
    value_eth: float = 0.0


def record_funding_event(ev: FundingEvent) -> None:
    """Idempotent insert. UNIQUE constraint protects against duplicates."""
    import time

    try:
        with _connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO wallet_funding
                    (wallet, source_addr, source_type, chain, tx_hash, ts, value_eth, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ev.wallet.lower(),
                    ev.source_addr.lower(),
                    ev.source_type,
                    ev.chain,
                    ev.tx_hash,
                    int(ev.ts),
                    float(ev.value_eth or 0.0),
                    int(time.time()),
                ),
            )
            conn.commit()
    except sqlite3.Error as e:
        # Don't let funding indexing break the analyze flow.
        log.debug("record_funding_event failed: %s", e)


@dataclass
class ClusterMatch:
    wallet: str
    source_addr: str
    source_type: str
    chain: str
    ts: int
    delta_seconds: int       # how far apart the funding was from our subject


@dataclass
class ClusterReport:
    address: str
    matches: list[ClusterMatch]
    distinct_wallets: int
    distinct_sources: int


def find_cluster(address: str) -> ClusterReport:
    """Return wallets that share funding events with `address`.

    Algorithm:
    1. Pull our subject's funding events.
    2. For each event, find other wallets funded from the same source on the
       same chain within ±CLUSTER_WINDOW_SEC.
    3. Aggregate, dedupe, sort by closeness.
    """
    address = address.lower()
    matches: list[ClusterMatch] = []

    with _connect() as conn:
        rows = conn.execute(
            "SELECT source_addr, source_type, chain, ts FROM wallet_funding WHERE wallet = ?",
            (address,),
        ).fetchall()
        if not rows:
            return ClusterReport(address=address, matches=[], distinct_wallets=0, distinct_sources=0)

        for r in rows:
            src = r["source_addr"]
            src_type = r["source_type"]
            chain = r["chain"]
            ts = int(r["ts"])
            window_lo = ts - CLUSTER_WINDOW_SEC
            window_hi = ts + CLUSTER_WINDOW_SEC

            siblings = conn.execute(
                """
                SELECT wallet, ts FROM wallet_funding
                WHERE source_addr = ?
                  AND chain = ?
                  AND ts BETWEEN ? AND ?
                  AND wallet != ?
                """,
                (src, chain, window_lo, window_hi, address),
            ).fetchall()

            for s in siblings:
                matches.append(ClusterMatch(
                    wallet=s["wallet"],
                    source_addr=src,
                    source_type=src_type,
                    chain=chain,
                    ts=int(s["ts"]),
                    delta_seconds=abs(int(s["ts"]) - ts),
                ))

    # Dedupe (same wallet might match multiple events) — keep the closest.
    by_wallet: dict[str, ClusterMatch] = {}
    for m in matches:
        prev = by_wallet.get(m.wallet)
        if prev is None or m.delta_seconds < prev.delta_seconds:
            by_wallet[m.wallet] = m
    deduped = sorted(by_wallet.values(), key=lambda m: m.delta_seconds)

    distinct_sources = len({(m.source_addr, m.chain) for m in deduped})
    return ClusterReport(
        address=address,
        matches=deduped,
        distinct_wallets=len(deduped),
        distinct_sources=distinct_sources,
    )
