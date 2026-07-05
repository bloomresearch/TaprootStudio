"""Append-only event log backed by SQLite — the system of record.

The graph store is a *derived projection* of this log. Every mutation is an
event; current state is reconstructed by replaying events. This gives full
auditability, time-travel, and the ability to rebuild any backend from scratch.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Iterator, Optional

from .schema import Belief, Edge, Provenance, Topic


class EventKind:
    BELIEF_UPSERT = "belief_upsert"
    BELIEF_STATUS = "belief_status"
    EDGE_UPSERT = "edge_upsert"
    EDGE_DELETE = "edge_delete"
    PROVENANCE = "provenance"
    TOPIC_UPSERT = "topic_upsert"


@dataclass
class Event:
    seq: int
    ts: float
    kind: str
    payload: dict


@dataclass
class GraphState:
    """The materialized projection of the event log."""

    beliefs: dict[str, Belief]
    edges: dict[str, Edge]
    provenance: list[Provenance]
    topics: dict[str, Topic]


class EventLog:
    def __init__(self, db_path: str = ":memory:") -> None:
        # check_same_thread=False + a lock so the MCP server (async) is safe.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = threading.RLock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    kind TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            self._conn.commit()

    def append(self, kind: str, payload: dict) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO events (ts, kind, payload) VALUES (?, ?, ?)",
                (time.time(), kind, json.dumps(payload)),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def iter_events(self) -> Iterator[Event]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT seq, ts, kind, payload FROM events ORDER BY seq ASC"
            ).fetchall()
        for seq, ts, kind, payload in rows:
            yield Event(seq=seq, ts=ts, kind=kind, payload=json.loads(payload))

    def project(self) -> GraphState:
        """Replay the log into current state."""
        beliefs: dict[str, Belief] = {}
        edges: dict[str, Edge] = {}
        provenance: list[Provenance] = []
        topics: dict[str, Topic] = {}

        for ev in self.iter_events():
            if ev.kind == EventKind.BELIEF_UPSERT:
                b = Belief(**ev.payload)
                beliefs[b.id] = b
            elif ev.kind == EventKind.BELIEF_STATUS:
                bid = ev.payload["belief_id"]
                if bid in beliefs:
                    beliefs[bid].status = ev.payload["status"]
                    if "confidence" in ev.payload and ev.payload["confidence"] is not None:
                        beliefs[bid].confidence = ev.payload["confidence"]
                    beliefs[bid].updated_at = ev.ts
            elif ev.kind == EventKind.EDGE_UPSERT:
                e = Edge(**ev.payload)
                edges[e.id] = e
            elif ev.kind == EventKind.EDGE_DELETE:
                edges.pop(ev.payload["edge_id"], None)
            elif ev.kind == EventKind.PROVENANCE:
                provenance.append(Provenance(**ev.payload))
            elif ev.kind == EventKind.TOPIC_UPSERT:
                t = Topic(**ev.payload)
                topics[t.id] = t

        return GraphState(
            beliefs=beliefs, edges=edges, provenance=provenance, topics=topics
        )

    def close(self) -> None:
        with self._lock:
            self._conn.close()
