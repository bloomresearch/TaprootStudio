from beliefgraph import BeliefGraphService, BeliefStatus, BeliefType
from beliefgraph.schema import EdgeType


def make_service():
    return BeliefGraphService(db_path=":memory:")


def test_ingest_creates_beliefs():
    svc = make_service()
    res = svc.ingest("We will use SQLAlchemy for the data layer. Maybe we add pgvector later.")
    assert len(res["added"]) == 2
    stats = svc.stats()
    assert stats["beliefs"] == 2
    # decision cue + hedge cue reflected in types/confidence
    beliefs = list(svc.state.beliefs.values())
    types = {b.type for b in beliefs}
    assert BeliefType.DECISION in types


def test_dedupe_reinforces():
    svc = make_service()
    svc.ingest("We will use SQLAlchemy for the data layer.")
    res2 = svc.ingest("We will use SQLAlchemy for the data layer.")
    assert res2["added"] == []
    assert res2["reinforced"]
    assert svc.stats()["beliefs"] == 1


def test_open_question_becomes_gap_then_answered():
    svc = make_service()
    svc.ingest("Which vector store should we use for retrieval?")
    q_gaps = [g for g in svc.get_gaps(top_k=50) if g.kind.value == "unanswered_question"]
    assert q_gaps, "open question should surface as a gap"

    # an answer that overlaps the question should auto-link and clear the gap
    svc.ingest("For retrieval we will use a vector store backed by sqlite-vec.")
    q_gaps_after = [
        g for g in svc.get_gaps(top_k=50) if g.kind.value == "unanswered_question"
    ]
    assert not q_gaps_after, "answered question should no longer be an unanswered gap"


def test_confidence_gap_and_confirm():
    svc = make_service()
    b = svc.add_belief(
        "The daemon runs as a local FastAPI process.",
        type=BeliefType.DECISION,
        confidence=0.4,
    )
    gaps = svc.get_gaps(top_k=50)
    assert any(b.id in g.belief_ids for g in gaps if g.kind.value == "confidence")

    svc.set_status(b.id, BeliefStatus.LOCKED, confidence=1.0)
    gaps_after = svc.get_gaps(top_k=50)
    assert not any(
        b.id in g.belief_ids for g in gaps_after if g.kind.value == "confidence"
    )


def test_coverage_gaps_present_when_empty():
    svc = make_service()
    gaps = svc.get_gaps(top_k=100)
    kinds = {g.kind.value for g in gaps}
    assert "coverage" in kinds


def test_contradiction_detected():
    svc = make_service()
    a = svc.add_belief("Storage should default to SQLite.", type=BeliefType.DECISION)
    b = svc.add_belief("Storage should default to Postgres.", type=BeliefType.DECISION)
    svc.add_edge(a.id, b.id, EdgeType.CONTRADICTS)
    contras = svc.get_contradictions()
    assert len(contras) == 1
    assert set(contras[0]["belief_ids"]) == {a.id, b.id}


def test_persistence_rebuild(tmp_path):
    db = str(tmp_path / "bg.db")
    svc = BeliefGraphService(db_path=db)
    svc.ingest("We will use Electron for the desktop shell.")
    n = svc.stats()["beliefs"]
    svc.close()

    svc2 = BeliefGraphService(db_path=db)
    assert svc2.stats()["beliefs"] == n  # rebuilt from the event log


def test_suggest_questions_ranked():
    svc = make_service()
    svc.ingest("Which auth model should we use?")
    qs = svc.suggest_questions(top_k=5)
    assert qs
    scores = [q["score"] for q in qs]
    assert scores == sorted(scores, reverse=True)
