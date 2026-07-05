"""Core epistemic data model for the belief graph.

The graph stores *beliefs* (typed claims with confidence + status) connected by
*typed edges*. This is deliberately richer than plain GraphRAG entities: every
node carries epistemic metadata so the gap engine can reason about what is
uncertain, unsupported, or contradicted.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _now() -> float:
    return time.time()


class BeliefType(str, Enum):
    """What kind of claim a belief represents."""

    DECISION = "decision"
    ASSUMPTION = "assumption"
    REQUIREMENT = "requirement"
    CONSTRAINT = "constraint"
    PREFERENCE = "preference"
    RISK = "risk"
    OPEN_QUESTION = "open_question"
    FACT = "fact"


class BeliefStatus(str, Enum):
    """Epistemic state of a belief. Drives gap detection."""

    PROPOSED = "proposed"      # extracted but not yet weighed
    ASSUMED = "assumed"        # believed, not confirmed by the user
    CONFIRMED = "confirmed"    # user confirmed
    LOCKED = "locked"          # binding decision
    REJECTED = "rejected"      # explicitly ruled out
    CONTRADICTED = "contradicted"  # conflicts with another live belief
    STALE = "stale"            # a dependency changed after this was set


class EdgeType(str, Enum):
    """Typed relationships between beliefs."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DEPENDS_ON = "depends_on"
    REFINES = "refines"
    ANSWERS = "answers"          # a belief that answers an open_question
    DERIVED_FROM = "derived_from"  # rationale / evidence link
    SCOPES = "scopes"           # belief scopes/belongs to a topic area


class Actor(str, Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


# Statuses that still count as "live" (not ruled out).
LIVE_STATUSES = frozenset(
    {
        BeliefStatus.PROPOSED,
        BeliefStatus.ASSUMED,
        BeliefStatus.CONFIRMED,
        BeliefStatus.LOCKED,
        BeliefStatus.CONTRADICTED,
        BeliefStatus.STALE,
    }
)

# Statuses the user has actively endorsed.
ENDORSED_STATUSES = frozenset({BeliefStatus.CONFIRMED, BeliefStatus.LOCKED})


class Belief(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("b"))
    statement: str
    type: BeliefType = BeliefType.FACT
    status: BeliefStatus = BeliefStatus.PROPOSED
    confidence: float = 0.5  # 0..1
    topic: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=_now)
    updated_at: float = Field(default_factory=_now)

    def is_live(self) -> bool:
        return self.status in LIVE_STATUSES

    def is_endorsed(self) -> bool:
        return self.status in ENDORSED_STATUSES


class Edge(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("e"))
    source_id: str
    target_id: str
    type: EdgeType
    confidence: float = 1.0
    created_at: float = Field(default_factory=_now)


class Provenance(BaseModel):
    """Where a belief came from — for audit and for grounding questions."""

    id: str = Field(default_factory=lambda: _new_id("p"))
    belief_id: str
    actor: Actor = Actor.AGENT
    source: str = "conversation"
    turn_id: Optional[str] = None
    quote: Optional[str] = None
    ts: float = Field(default_factory=_now)


class Topic(BaseModel):
    """An ontology anchor used for coverage-gap detection."""

    id: str
    name: str
    description: str = ""
    keywords: list[str] = Field(default_factory=list)
    importance: float = 1.0  # weights coverage-gap scoring
