"""会话聚合测试：只负责序号分配与上下文指针，不持有历史。"""

from ai_srpg.models import NoneEvent
from ai_srpg.session.player_session import PlayerSession


###############################################################################
def test_new_session_starts_at_zero() -> None:
    session = PlayerSession(user_name="alice")

    assert session.event_sequence == 0
    assert session.actor is None
    assert session.game is None
    assert not hasattr(session, "session_messages")


def test_add_agent_event_allocates_monotonic_sequence() -> None:
    session = PlayerSession(user_name="alice")

    first = session.add_agent_event(NoneEvent(message="a"))
    second = session.add_agent_event(NoneEvent(message="b"))

    assert (first.sequence_id, second.sequence_id) == (1, 2)
    assert session.event_sequence == 2


def test_add_agent_event_uses_context_as_defaults() -> None:
    session = PlayerSession(user_name="alice")
    session.set_context(actor="角色.无名", game="Game1")

    message = session.add_agent_event(NoneEvent(message="a"), job_id=9)

    assert (message.actor, message.game_name) == ("角色.无名", "Game1")
    assert message.job_id == 9


def test_explicit_values_override_context() -> None:
    session = PlayerSession(user_name="alice")
    session.set_context(actor="角色.无名", game="Game1")

    message = session.add_agent_event(
        NoneEvent(message="a"), game_name="Game2", actor="角色.甲"
    )

    assert (message.actor, message.game_name) == ("角色.甲", "Game2")


def test_restored_session_continues_from_persisted_cursor() -> None:
    session = PlayerSession(user_name="alice", event_sequence=41)

    message = session.add_agent_event(NoneEvent(message="a"))

    assert message.sequence_id == 42
