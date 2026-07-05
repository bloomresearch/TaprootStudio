"""MCP server exposing the belief graph as tools an agent can call.

Run:  belief-graph-mcp            (stdio transport, for Devin / Claude Desktop)
Env:
  BELIEFGRAPH_DB      path to the SQLite event log (default: ./belief_graph.db)
  BELIEFGRAPH_BACKEND local | graphiti          (default: local)
  GEMINI_API_KEY      enables LLM belief extraction (else rule-based fallback)
"""

from __future__ import annotations

import os
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .schema import BeliefStatus, BeliefType, EdgeType
from .service import BeliefGraphService


def build_service() -> BeliefGraphService:
    db_path = os.environ.get("BELIEFGRAPH_DB", "belief_graph.db")

    extractor = None
    if os.environ.get("GEMINI_API_KEY"):
        try:
            from .extract import GeminiExtractor

            extractor = GeminiExtractor()
        except Exception:
            extractor = None  # fall back to rule-based

    store = None
    if os.environ.get("BELIEFGRAPH_BACKEND", "local").lower() == "graphiti":
        try:
            from .backends.graphiti_backend import GraphitiGraphStore

            store = GraphitiGraphStore()
        except Exception:
            store = None  # fall back to local

    return BeliefGraphService(db_path=db_path, store=store, extractor=extractor)


mcp = FastMCP("belief-graph")
_service: Optional[BeliefGraphService] = None


def service() -> BeliefGraphService:
    global _service
    if _service is None:
        _service = build_service()
    return _service


@mcp.tool()
def ingest(text: str, actor: str = "user", turn_id: str = "") -> dict:
    """Extract beliefs from a message and merge them into the graph.

    Call this on every substantive user/agent message to keep the graph live.
    Returns which beliefs were added, reinforced, or used to answer open questions.
    """
    from .schema import Actor

    actor_enum = Actor(actor) if actor in Actor._value2member_map_ else Actor.USER
    return service().ingest(text, actor=actor_enum, turn_id=turn_id or None)


@mcp.tool()
def get_gaps(top_k: int = 10, kind: str = "") -> list[dict]:
    """Return ranked knowledge gaps (what's uncertain/missing/contradicted).

    Optional kind filter: coverage | confidence | missing_rationale |
    unanswered_question | requirement_unaddressed | contradiction.
    """
    gaps = service().get_gaps(top_k=top_k, kind=kind or None)
    return [
        {
            "kind": g.kind.value,
            "score": g.score,
            "description": g.description,
            "question": g.suggested_question,
            "belief_ids": g.belief_ids,
            "topic_id": g.topic_id,
        }
        for g in gaps
    ]


@mcp.tool()
def suggest_questions(top_k: int = 5) -> list[dict]:
    """Return the top-N grounded questions to ask next, derived from the gaps."""
    return service().suggest_questions(top_k=top_k)


@mcp.tool()
def query(text: str, top_k: int = 8) -> list[dict]:
    """Retrieve the most relevant beliefs for a free-text query."""
    return [b.model_dump(mode="json") for b in service().query(text, top_k=top_k)]


@mcp.tool()
def add_belief(
    statement: str,
    type: str = "fact",
    status: str = "proposed",
    confidence: float = 0.5,
    topic: str = "",
) -> dict:
    """Add a single belief explicitly (bypassing extraction)."""
    b = service().add_belief(
        statement=statement,
        type=BeliefType(type),
        status=BeliefStatus(status),
        confidence=confidence,
        topic=topic or None,
    )
    return b.model_dump(mode="json")


@mcp.tool()
def add_edge(source_id: str, target_id: str, type: str) -> dict:
    """Link two beliefs. type: supports|contradicts|depends_on|refines|answers|derived_from|scopes."""
    e = service().add_edge(source_id, target_id, EdgeType(type))
    return e.model_dump(mode="json")


@mcp.tool()
def set_status(belief_id: str, status: str, confidence: float = -1.0) -> dict:
    """Update a belief's epistemic status (confirm/lock/reject/etc.)."""
    conf = None if confidence < 0 else confidence
    b = service().set_status(belief_id, BeliefStatus(status), confidence=conf)
    return b.model_dump(mode="json") if b else {"error": "belief not found"}


@mcp.tool()
def get_contradictions() -> list[dict]:
    """List live contradictions that need resolving."""
    return service().get_contradictions()


@mcp.tool()
def get_belief(belief_id: str) -> dict:
    """Fetch one belief plus its graph neighbors."""
    svc = service()
    b = svc.get_belief(belief_id)
    if not b:
        return {"error": "belief not found"}
    return {
        "belief": b.model_dump(mode="json"),
        "neighbors": [n.model_dump(mode="json") for n in svc.neighbors(belief_id)],
    }


@mcp.tool()
def stats() -> dict:
    """Summary counts of the current belief graph."""
    return service().stats()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
