"""belief-graph: an epistemic belief graph with knowledge-gap detection over MCP."""

from .schema import (
    Actor,
    Belief,
    BeliefStatus,
    BeliefType,
    Edge,
    EdgeType,
    Provenance,
    Topic,
)
from .service import BeliefGraphService
from .gaps import Gap, GapKind

__all__ = [
    "BeliefGraphService",
    "Belief",
    "BeliefType",
    "BeliefStatus",
    "Edge",
    "EdgeType",
    "Provenance",
    "Topic",
    "Actor",
    "Gap",
    "GapKind",
]

__version__ = "0.1.0"
