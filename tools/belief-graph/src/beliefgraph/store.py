"""IGraphStore — the swappable retrieval/graph substrate.

The belief/epistemic layer and the gap engine are the product; the graph engine
behind this interface is a commodity. A local NetworkX backend ships by default;
a Graphiti (Kuzu) backend implements the same contract.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .eventlog import GraphState
from .schema import Belief


@runtime_checkable
class IGraphStore(Protocol):
    def load_state(self, state: GraphState) -> None:
        """(Re)load the full materialized state. Called after mutations."""
        ...

    def query(self, text: str, top_k: int = 8) -> list[Belief]:
        """Return the most relevant beliefs for a free-text query."""
        ...

    def neighbors(self, belief_id: str) -> list[Belief]:
        """Return beliefs directly connected to the given belief."""
        ...

    def centrality(self) -> dict[str, float]:
        """Return a per-belief importance score in [0, 1] (e.g. PageRank)."""
        ...

    def close(self) -> None:
        ...
