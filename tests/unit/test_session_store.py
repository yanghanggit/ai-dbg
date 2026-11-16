"""用户会话历史存储与领域事件 sink 的单测。"""

from pathlib import Path

from ai_dbg.models import NoneEvent, PlayerSession
from ai_dbg.session import PlayerSessionEventSink, SessionStore


def _event(message: str) -> NoneEvent:
    return NoneEvent(message=message)


def test_session_store_round_trip_and_sequence(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    session = store.load_or_create("alice", actor="hero", game="demo")
    first = session.add_agent_event(_event("first"))
    store.append(session, first)
    second = session.add_agent_event(_event("second"))
    store.append(session, second)
    store.save_meta(session)

    restored = store.load("alice")

    assert restored.name == "alice"
    assert restored.actor == "hero"
    assert restored.game == "demo"
    assert restored.event_sequence == 2
    assert [m.sequence_id for m in restored.session_messages] == [1, 2]
    contents = []
    for message in restored.session_messages:
        assert message.agent_event is not None
        contents.append(message.agent_event.message)
    assert contents == ["first", "second"]


def test_session_store_does_not_reset_across_context_switch(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    session = store.load_or_create("alice", actor="hero", game="demo")
    store.append(session, session.add_agent_event(_event("old game")))
    store.save_meta(session)

    session.set_context(actor="new_hero", game="demo-2")
    store.append(session, session.add_agent_event(_event("new game")))
    store.save_meta(session)

    restored = store.load("alice")

    assert restored.event_sequence == 2
    assert restored.game == "demo-2"
    assert restored.actor == "new_hero"
    assert [m.game_name for m in restored.session_messages] == ["demo", "demo-2"]
    assert [m.actor for m in restored.session_messages] == ["hero", "new_hero"]


def test_session_event_sink_persists_job_and_context(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    session = PlayerSession(name="alice", actor="hero", game="demo")
    sink = PlayerSessionEventSink(session, store, job_id=42)

    sink.publish(_event("played a card"))

    restored = store.load("alice")
    assert restored.event_sequence == 1
    message = restored.session_messages[0]
    assert message.job_id == 42
    assert message.game_name == "demo"
    assert message.actor == "hero"
    assert message.agent_event is not None
    assert message.agent_event.message == "played a card"


def test_load_or_create_keeps_existing_context(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    first = store.load_or_create("alice", actor="hero", game="demo")
    store.save_meta(first)

    second = store.load_or_create("alice", actor="other", game="other")

    assert second.actor == "hero"
    assert second.game == "demo"
