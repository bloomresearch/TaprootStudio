"""Seed the belief graph with locked Taproot Studio decisions, then print the
top knowledge gaps + suggested next questions.

Run:  python examples/seed_taproot.py
"""

from __future__ import annotations

from beliefgraph import BeliefGraphService, BeliefStatus, BeliefType

LOCKED_DECISIONS = [
    "Taproot Studio ships as an Electron desktop application.",
    "The LLM layer is multi-provider with Gemini as the first-class default.",
    "A local Python daemon (FastAPI) hosts the execution engine.",
    "Flows are stored globally and imported by reference.",
    "SQLAlchemy is the data-access layer, defaulting to SQLite.",
    "Vectors use sqlite-vec by default and pgvector when on Postgres.",
    "Python tools run in an isolated subprocess/venv sandbox.",
    "The execution engine adopts and extends the existing flowcore Python engine.",
]

FACTS = [
    "The workspace uses a 5-surface cross layout navigated by a swap-rotation model.",
    "The Orchestrator is a default-but-editable flow whose per-surface behavior is expressed via agent States.",
    "The design language is dark professional neumorphism from Reaction Studio.",
    "flowcore executes async with multi-input joins and first-class loop-back but is not yet parallel.",
]


def main() -> None:
    svc = BeliefGraphService(db_path=":memory:")

    for stmt in LOCKED_DECISIONS:
        svc.add_belief(stmt, type=BeliefType.DECISION, status=BeliefStatus.LOCKED, confidence=1.0)
    for stmt in FACTS:
        svc.add_belief(stmt, type=BeliefType.FACT, status=BeliefStatus.CONFIRMED, confidence=0.9)

    print("=== STATS ===")
    print(svc.stats())

    print("\n=== TOP KNOWLEDGE GAPS ===")
    for g in svc.get_gaps(top_k=8):
        print(f"[{g.score:>5}] {g.kind.value:22} {g.description}")

    print("\n=== SUGGESTED NEXT QUESTIONS ===")
    for i, q in enumerate(svc.suggest_questions(top_k=6), 1):
        print(f"{i}. ({q['kind']}, {q['score']}) {q['question']}")

    svc.close()


if __name__ == "__main__":
    main()
