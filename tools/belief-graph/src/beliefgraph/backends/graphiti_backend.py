"""Graphiti-backed graph store (EXPERIMENTAL).

Graphiti (getzep/graphiti) is a temporally-aware, incrementally-updated knowledge
graph built for agent memory — its automatic edge invalidation maps naturally onto
belief revision. Here it is used as the *semantic retrieval* substrate, while the
belief graph's own typed structure (centrality, neighbors) is kept in a local
NetworkX projection. This keeps the epistemic layer engine-independent.

Requires:  pip install "belief-graph[graphiti,gemini]"  and  GEMINI_API_KEY
Uses Graphiti's embedded Kuzu driver, so no Neo4j/Docker is needed.

This backend is untested in CI (needs an API key + native deps); the local backend
is the default. It is written defensively and lazy-imported so it never affects the
local path.
"""

from __future__ import annotations

import asyncio
import os
import threading
from typing import Optional

from ..eventlog import GraphState
from ..schema import Belief
from ..text import jaccard
from .local import LocalGraphStore


class _Loop:
    """A dedicated background asyncio loop so sync MCP tools can drive Graphiti."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self._thread.start()

    def run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result()


class GraphitiGraphStore:
    def __init__(
        self,
        db_path: str = "belief_graph_kuzu",
        model: str = "gemini-2.0-flash",
    ) -> None:
        # Lazy imports so importing this module never hard-fails.
        from graphiti_core import Graphiti
        from graphiti_core.driver.kuzu_driver import KuzuDriver
        from graphiti_core.embedder.gemini import GeminiEmbedder, GeminiEmbedderConfig
        from graphiti_core.llm_client.gemini_client import GeminiClient, LLMConfig

        api_key = os.environ["GEMINI_API_KEY"]
        self._structure = LocalGraphStore()  # centrality + neighbors over belief ids
        self._loop = _Loop()
        self._synced: set[str] = set()
        self._beliefs: dict[str, Belief] = {}

        driver = KuzuDriver(db=db_path)
        self._graphiti = Graphiti(
            graph_driver=driver,
            llm_client=GeminiClient(config=LLMConfig(api_key=api_key, model=model)),
            embedder=GeminiEmbedder(
                config=GeminiEmbedderConfig(
                    api_key=api_key, embedding_model="text-embedding-004"
                )
            ),
        )
        self._loop.run(self._graphiti.build_indices_and_constraints())

    def load_state(self, state: GraphState) -> None:
        self._structure.load_state(state)
        self._beliefs = dict(state.beliefs)
        # Incrementally push newly-seen beliefs into Graphiti as episodes.
        for bid, belief in state.beliefs.items():
            if bid in self._synced:
                continue
            try:
                from graphiti_core.nodes import EpisodeType

                self._loop.run(
                    self._graphiti.add_episode(
                        name=bid,
                        episode_body=belief.statement,
                        source=EpisodeType.text,
                        source_description=f"{belief.type.value}:{belief.status.value}",
                        reference_time=self._now(),
                    )
                )
                self._synced.add(bid)
            except Exception:
                # Best-effort sync; retrieval degrades gracefully to local.
                break

    @staticmethod
    def _now():
        from datetime import datetime, timezone

        return datetime.now(timezone.utc)

    def query(self, text: str, top_k: int = 8) -> list[Belief]:
        try:
            results = self._loop.run(self._graphiti.search(text))
        except Exception:
            return self._structure.query(text, top_k=top_k)

        # Map Graphiti's semantic hits back onto our beliefs.
        matched: list[Belief] = []
        seen: set[str] = set()
        for r in results:
            fact = getattr(r, "fact", None) or getattr(r, "name", "") or str(r)
            best: tuple[float, Optional[Belief]] = (0.0, None)
            for b in self._beliefs.values():
                sim = jaccard(fact, b.statement)
                if sim > best[0]:
                    best = (sim, b)
            if best[1] is not None and best[1].id not in seen:
                seen.add(best[1].id)
                matched.append(best[1])
            if len(matched) >= top_k:
                break
        return matched or self._structure.query(text, top_k=top_k)

    def neighbors(self, belief_id: str) -> list[Belief]:
        return self._structure.neighbors(belief_id)

    def centrality(self) -> dict[str, float]:
        return self._structure.centrality()

    def close(self) -> None:
        try:
            self._loop.run(self._graphiti.close())
        except Exception:
            pass
        self._structure.close()
