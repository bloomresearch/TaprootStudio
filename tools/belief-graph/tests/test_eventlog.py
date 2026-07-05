from beliefgraph.eventlog import EventKind, EventLog
from beliefgraph.schema import Belief, BeliefStatus, BeliefType, Edge, EdgeType


def test_append_and_project():
    log = EventLog(":memory:")
    b = Belief(statement="A", type=BeliefType.DECISION)
    log.append(EventKind.BELIEF_UPSERT, b.model_dump(mode="json"))
    state = log.project()
    assert b.id in state.beliefs
    assert state.beliefs[b.id].statement == "A"


def test_status_update_projection():
    log = EventLog(":memory:")
    b = Belief(statement="A")
    log.append(EventKind.BELIEF_UPSERT, b.model_dump(mode="json"))
    log.append(
        EventKind.BELIEF_STATUS,
        {"belief_id": b.id, "status": BeliefStatus.LOCKED.value, "confidence": 0.9},
    )
    state = log.project()
    assert state.beliefs[b.id].status == BeliefStatus.LOCKED
    assert state.beliefs[b.id].confidence == 0.9


def test_edge_upsert_and_delete():
    log = EventLog(":memory:")
    e = Edge(source_id="x", target_id="y", type=EdgeType.SUPPORTS)
    log.append(EventKind.EDGE_UPSERT, e.model_dump(mode="json"))
    assert e.id in log.project().edges
    log.append(EventKind.EDGE_DELETE, {"edge_id": e.id})
    assert e.id not in log.project().edges
