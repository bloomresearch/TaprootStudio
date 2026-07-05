"""Local, zero-dependency graph store: NetworkX + token-overlap retrieval.

Good enough to exercise the full ingest -> gap -> question loop deterministically
with no external services or API keys. PageRank supplies belief centrality.
"""

from __future__ import annotations

import math
import re
from collections import Counter

import networkx as nx

from ..eventlog import GraphState
from ..schema import Belief

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_STOPWORDS = frozenset(
    """
    the a an and or of to in on for with is are be by as at it this that these those
    we you they i he she our your their its from into will would should could can may
    """.split()
)


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


class LocalGraphStore:
    def __init__(self) -> None:
        self._beliefs: dict[str, Belief] = {}
        self._graph = nx.DiGraph()
        self._df: Counter[str] = Counter()  # document frequency for tf-idf-ish scoring

    def load_state(self, state: GraphState) -> None:
        self._beliefs = dict(state.beliefs)
        g = nx.DiGraph()
        for bid in self._beliefs:
            g.add_node(bid)
        for edge in state.edges.values():
            if edge.source_id in self._beliefs and edge.target_id in self._beliefs:
                g.add_edge(edge.source_id, edge.target_id, type=edge.type)
        self._graph = g

        self._df = Counter()
        for b in self._beliefs.values():
            for tok in set(_tokens(b.statement)):
                self._df[tok] += 1

    def _score(self, query_tokens: list[str], belief: Belief) -> float:
        if not query_tokens:
            return 0.0
        n = max(len(self._beliefs), 1)
        btokens = Counter(_tokens(belief.statement))
        score = 0.0
        for qt in query_tokens:
            if qt in btokens:
                idf = math.log((n + 1) / (self._df.get(qt, 0) + 1)) + 1.0
                score += btokens[qt] * idf
        return score

    def query(self, text: str, top_k: int = 8) -> list[Belief]:
        qt = _tokens(text)
        scored = [
            (self._score(qt, b), b)
            for b in self._beliefs.values()
        ]
        scored = [(s, b) for s, b in scored if s > 0]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [b for _, b in scored[:top_k]]

    def neighbors(self, belief_id: str) -> list[Belief]:
        if belief_id not in self._graph:
            return []
        ids = set(self._graph.predecessors(belief_id)) | set(
            self._graph.successors(belief_id)
        )
        return [self._beliefs[i] for i in ids if i in self._beliefs]

    def centrality(self) -> dict[str, float]:
        if len(self._graph) == 0:
            return {}
        try:
            pr = nx.pagerank(self._graph, alpha=0.85)
        except Exception:
            # Fallback: degree centrality (e.g. empty graph / convergence issues).
            pr = nx.degree_centrality(self._graph)
        if not pr:
            return {}
        hi = max(pr.values()) or 1.0
        return {k: v / hi for k, v in pr.items()}

    def close(self) -> None:  # nothing to release
        pass
