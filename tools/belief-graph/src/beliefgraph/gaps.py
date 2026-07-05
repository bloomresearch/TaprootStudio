"""The gap engine — the heart of the belief graph.

Turns the current belief state into a *ranked list of knowledge gaps*, each with a
grounded, phrased question. Ranking favors gaps that are both important
(high graph centrality / topic importance) and uncertain (low confidence /
unconfirmed / contradicted).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from .eventlog import GraphState
from .schema import (
    Belief,
    BeliefStatus,
    BeliefType,
    Edge,
    EdgeType,
    Topic,
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class GapKind(str, Enum):
    COVERAGE = "coverage"
    CONFIDENCE = "confidence"
    MISSING_RATIONALE = "missing_rationale"
    UNANSWERED_QUESTION = "unanswered_question"
    REQUIREMENT_UNADDRESSED = "requirement_unaddressed"
    CONTRADICTION = "contradiction"


@dataclass
class Gap:
    kind: GapKind
    description: str
    suggested_question: str
    score: float
    belief_ids: list[str] = field(default_factory=list)
    topic_id: str | None = None


def match_topic(statement: str, ontology: list[Topic]) -> str | None:
    """Assign a statement to the best-matching ontology topic by keyword hits."""
    low = statement.lower()
    best: tuple[float, str | None] = (0.0, None)
    for topic in ontology:
        hits = sum(1 for kw in topic.keywords if kw in low)
        if hits:
            weight = hits * topic.importance
            if weight > best[0]:
                best = (weight, topic.id)
    return best[1]


def _dependents(belief_id: str, edges: list[Edge]) -> int:
    return sum(
        1
        for e in edges
        if e.target_id == belief_id
        and e.type in (EdgeType.DEPENDS_ON, EdgeType.REFINES)
    )


def _has_out_edge(belief_id: str, edges: list[Edge], types: set[EdgeType]) -> bool:
    return any(e.source_id == belief_id and e.type in types for e in edges)


def _has_in_edge(belief_id: str, edges: list[Edge], types: set[EdgeType]) -> bool:
    return any(e.target_id == belief_id and e.type in types for e in edges)


def compute_gaps(
    state: GraphState,
    centrality: dict[str, float],
    ontology: list[Topic],
) -> list[Gap]:
    beliefs = list(state.beliefs.values())
    edges = list(state.edges.values())
    live = [b for b in beliefs if b.is_live()]
    gaps: list[Gap] = []

    # --- 1. Coverage gaps: ontology topics with weak/no belief coverage ---
    coverage: dict[str, int] = {t.id: 0 for t in ontology}
    endorsed_coverage: dict[str, int] = {t.id: 0 for t in ontology}
    for b in live:
        tid = b.topic or match_topic(b.statement, ontology)
        if tid in coverage:
            coverage[tid] += 1
            if b.is_endorsed():
                endorsed_coverage[tid] += 1

    for topic in ontology:
        cov = coverage[topic.id]
        endorsed = endorsed_coverage[topic.id]
        if endorsed >= 1:
            continue  # topic has a confirmed/locked belief — considered covered
        # weaker coverage -> higher score; importance amplifies
        deficit = 1.0 if cov == 0 else 0.5
        score = round(topic.importance * deficit, 4)
        gaps.append(
            Gap(
                kind=GapKind.COVERAGE,
                topic_id=topic.id,
                description=f"Topic '{topic.name}' has no confirmed belief "
                f"({cov} live, {endorsed} endorsed).",
                suggested_question=(
                    f"We haven't locked anything on **{topic.name}**. "
                    f"{topic.description} How should this work?"
                ),
                score=score,
            )
        )

    # --- 2. Confidence gaps: important-but-uncertain live beliefs ---
    for b in live:
        c = centrality.get(b.id, 0.0)
        uncertain = (
            b.status in (BeliefStatus.PROPOSED, BeliefStatus.ASSUMED)
            or b.confidence < 0.5
        )
        if not uncertain:
            continue
        deps = _dependents(b.id, edges)
        # +0.15 base so isolated-but-uncertain beliefs still surface a little
        score = round((c + 0.15) * (1.0 - b.confidence) * (1 + deps), 4)
        gaps.append(
            Gap(
                kind=GapKind.CONFIDENCE,
                belief_ids=[b.id],
                description=f"'{b.statement}' is {b.status.value} "
                f"(confidence {b.confidence}, {deps} dependents).",
                suggested_question=(
                    f"You mentioned: \"{b.statement}\" — is that confirmed, or "
                    f"should it be refined or dropped?"
                ),
                score=score,
            )
        )

    # --- 3. Structural gaps ---
    for b in live:
        c = centrality.get(b.id, 0.0)
        if b.type is BeliefType.DECISION and not _has_out_edge(
            b.id, edges, {EdgeType.DERIVED_FROM}
        ):
            gaps.append(
                Gap(
                    kind=GapKind.MISSING_RATIONALE,
                    belief_ids=[b.id],
                    description=f"Decision has no recorded rationale: '{b.statement}'.",
                    suggested_question=f"What's the rationale behind deciding: \"{b.statement}\"?",
                    score=round(0.4 + 0.4 * c, 4),
                )
            )
        if b.type is BeliefType.OPEN_QUESTION and not _has_in_edge(
            b.id, edges, {EdgeType.ANSWERS}
        ):
            gaps.append(
                Gap(
                    kind=GapKind.UNANSWERED_QUESTION,
                    belief_ids=[b.id],
                    description=f"Open question is unanswered: '{b.statement}'.",
                    suggested_question=b.statement,
                    score=round(0.6 + 0.4 * c, 4),
                )
            )
        if b.type is BeliefType.REQUIREMENT and not (
            _has_in_edge(b.id, edges, {EdgeType.ANSWERS, EdgeType.SUPPORTS})
            or _has_out_edge(b.id, edges, {EdgeType.REFINES})
        ):
            gaps.append(
                Gap(
                    kind=GapKind.REQUIREMENT_UNADDRESSED,
                    belief_ids=[b.id],
                    description=f"Requirement has no addressing decision: '{b.statement}'.",
                    suggested_question=(
                        f"Requirement \"{b.statement}\" isn't addressed by any "
                        f"decision yet — how should it be satisfied?"
                    ),
                    score=round(0.45 + 0.4 * c, 4),
                )
            )

    # --- 4. Contradictions between live beliefs ---
    for e in edges:
        if e.type is not EdgeType.CONTRADICTS:
            continue
        a = state.beliefs.get(e.source_id)
        b = state.beliefs.get(e.target_id)
        if not a or not b or not a.is_live() or not b.is_live():
            continue
        ca = centrality.get(a.id, 0.0)
        cb = centrality.get(b.id, 0.0)
        gaps.append(
            Gap(
                kind=GapKind.CONTRADICTION,
                belief_ids=[a.id, b.id],
                description=f"Contradiction: '{a.statement}' vs '{b.statement}'.",
                suggested_question=(
                    f"These conflict — which holds? (1) \"{a.statement}\" "
                    f"vs (2) \"{b.statement}\"?"
                ),
                score=round(0.8 + 0.2 * (ca + cb), 4),
            )
        )

    gaps.sort(key=lambda g: g.score, reverse=True)
    return gaps
