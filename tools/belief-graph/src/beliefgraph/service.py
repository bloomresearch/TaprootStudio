"""BeliefGraphService — orchestrates the event log, graph store, extractor, and
gap engine into the continuous ingest -> gap -> question loop.
"""

from __future__ import annotations

from typing import Optional

from .eventlog import EventKind, EventLog
from .extract import BeliefExtractor, ExtractedBelief, RuleBasedExtractor
from .gaps import Gap, compute_gaps, match_topic
from .ontology import default_ontology
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
from .store import IGraphStore
from .text import jaccard

_DUP_THRESHOLD = 0.82       # >= this Jaccard = treat as the same belief
_ANSWER_THRESHOLD = 0.4     # >= this = a statement plausibly answers an open question


class BeliefGraphService:
    def __init__(
        self,
        db_path: str = ":memory:",
        store: Optional[IGraphStore] = None,
        extractor: Optional[BeliefExtractor] = None,
        ontology: Optional[list[Topic]] = None,
    ) -> None:
        from .backends.local import LocalGraphStore

        self.log = EventLog(db_path)
        self.store: IGraphStore = store or LocalGraphStore()
        self.extractor: BeliefExtractor = extractor or RuleBasedExtractor()
        self._base_ontology = ontology or default_ontology()
        self._centrality: dict[str, float] = {}
        self.state = self.log.project()
        self._reload()

    # ------------------------------------------------------------------ core
    def _reload(self) -> None:
        self.state = self.log.project()
        self.store.load_state(self.state)
        self._centrality = self.store.centrality()

    def effective_ontology(self) -> list[Topic]:
        merged = {t.id: t for t in self._base_ontology}
        merged.update(self.state.topics)  # custom topics override/extend defaults
        return list(merged.values())

    # -------------------------------------------------------------- mutations
    def add_belief(
        self,
        statement: str,
        type: BeliefType = BeliefType.FACT,
        status: BeliefStatus = BeliefStatus.PROPOSED,
        confidence: float = 0.5,
        topic: Optional[str] = None,
        actor: Actor = Actor.AGENT,
        turn_id: Optional[str] = None,
        quote: Optional[str] = None,
    ) -> Belief:
        if topic is None:
            topic = match_topic(statement, self.effective_ontology())
        belief = Belief(
            statement=statement,
            type=type,
            status=status,
            confidence=confidence,
            topic=topic,
        )
        self.log.append(EventKind.BELIEF_UPSERT, belief.model_dump(mode="json"))
        self.log.append(
            EventKind.PROVENANCE,
            Provenance(
                belief_id=belief.id, actor=actor, turn_id=turn_id, quote=quote
            ).model_dump(mode="json"),
        )
        self._reload()
        return belief

    def add_edge(
        self, source_id: str, target_id: str, type: EdgeType, confidence: float = 1.0
    ) -> Edge:
        edge = Edge(
            source_id=source_id, target_id=target_id, type=type, confidence=confidence
        )
        self.log.append(EventKind.EDGE_UPSERT, edge.model_dump(mode="json"))
        self._reload()
        return edge

    def set_status(
        self,
        belief_id: str,
        status: BeliefStatus,
        confidence: Optional[float] = None,
    ) -> Optional[Belief]:
        if belief_id not in self.state.beliefs:
            return None
        self.log.append(
            EventKind.BELIEF_STATUS,
            {"belief_id": belief_id, "status": status.value, "confidence": confidence},
        )
        self._reload()
        return self.state.beliefs.get(belief_id)

    def add_topic(self, topic: Topic) -> Topic:
        self.log.append(EventKind.TOPIC_UPSERT, topic.model_dump(mode="json"))
        self._reload()
        return topic

    # ----------------------------------------------------------------- ingest
    def _find_duplicate(self, statement: str) -> Optional[Belief]:
        best: tuple[float, Optional[Belief]] = (0.0, None)
        for b in self.state.beliefs.values():
            sim = jaccard(statement, b.statement)
            if sim > best[0]:
                best = (sim, b)
        return best[1] if best[0] >= _DUP_THRESHOLD else None

    def _open_questions(self) -> list[Belief]:
        return [
            b
            for b in self.state.beliefs.values()
            if b.type is BeliefType.OPEN_QUESTION and b.is_live()
        ]

    def ingest(
        self,
        text: str,
        actor: Actor = Actor.USER,
        turn_id: Optional[str] = None,
    ) -> dict:
        """Extract beliefs from text, upsert them, and auto-link answers.

        Returns a summary of what changed.
        """
        extracted: list[ExtractedBelief] = self.extractor.extract(text)
        added: list[Belief] = []
        merged: list[str] = []
        answered: list[str] = []

        # snapshot open questions *before* this batch, to link answers against
        open_qs = self._open_questions()

        for ex in extracted:
            dup = self._find_duplicate(ex.statement)
            if dup is not None:
                # reinforce provenance instead of creating a near-identical belief
                self.log.append(
                    EventKind.PROVENANCE,
                    Provenance(
                        belief_id=dup.id, actor=actor, turn_id=turn_id, quote=ex.statement
                    ).model_dump(mode="json"),
                )
                merged.append(dup.id)
                continue

            belief = self.add_belief(
                statement=ex.statement,
                type=ex.type,
                status=BeliefStatus.PROPOSED,
                confidence=ex.confidence,
                topic=ex.topic,
                actor=actor,
                turn_id=turn_id,
                quote=ex.statement,
            )
            added.append(belief)

            # auto-link: does this new (non-question) belief answer an open question?
            if belief.type is not BeliefType.OPEN_QUESTION:
                for q in open_qs:
                    if jaccard(belief.statement, q.statement) >= _ANSWER_THRESHOLD:
                        self.add_edge(belief.id, q.id, EdgeType.ANSWERS)
                        answered.append(q.id)

        return {
            "added": [b.id for b in added],
            "added_beliefs": [b.model_dump(mode="json") for b in added],
            "reinforced": merged,
            "answered_questions": answered,
        }

    # ------------------------------------------------------------------ reads
    def query(self, text: str, top_k: int = 8) -> list[Belief]:
        return self.store.query(text, top_k=top_k)

    def get_belief(self, belief_id: str) -> Optional[Belief]:
        return self.state.beliefs.get(belief_id)

    def neighbors(self, belief_id: str) -> list[Belief]:
        return self.store.neighbors(belief_id)

    def get_gaps(self, top_k: int = 10, kind: Optional[str] = None) -> list[Gap]:
        gaps = compute_gaps(self.state, self._centrality, self.effective_ontology())
        if kind:
            gaps = [g for g in gaps if g.kind.value == kind]
        return gaps[:top_k]

    def suggest_questions(self, top_k: int = 5) -> list[dict]:
        return [
            {
                "question": g.suggested_question,
                "kind": g.kind.value,
                "score": g.score,
                "why": g.description,
                "belief_ids": g.belief_ids,
                "topic_id": g.topic_id,
            }
            for g in self.get_gaps(top_k=top_k)
        ]

    def get_contradictions(self) -> list[dict]:
        return [
            {
                "belief_ids": g.belief_ids,
                "description": g.description,
                "question": g.suggested_question,
            }
            for g in self.get_gaps(top_k=1000, kind="contradiction")
        ]

    def stats(self) -> dict:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for b in self.state.beliefs.values():
            by_type[b.type.value] = by_type.get(b.type.value, 0) + 1
            by_status[b.status.value] = by_status.get(b.status.value, 0) + 1
        return {
            "beliefs": len(self.state.beliefs),
            "edges": len(self.state.edges),
            "by_type": by_type,
            "by_status": by_status,
            "topics": len(self.effective_ontology()),
        }

    def close(self) -> None:
        self.store.close()
        self.log.close()
