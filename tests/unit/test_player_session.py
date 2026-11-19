"""会话聚合测试：只保存游标与上下文指针，序号由房间分配。"""

from ai_srpg.models import NoneEvent
from ai_srpg.session.player_session import PlayerSession


###############################################################################
def test_new_session_starts_at_zero() -> None:
    session = PlayerSession(user_name="alice", room_id="alice")

    assert session.event_sequence == 0
    assert session.actor is None
    assert session.game is None
    assert not hasattr(session, "session_messages")


def test_set_context_does_not_touch_cursor() -> None:
    session = PlayerSession(user_name="alice", room_id="alice", event_sequence=5)

    session.set_context(actor="角色.无名", game="Game1")

    assert (session.actor, session.game) == ("角色.无名", "Game1")
    assert session.event_sequence == 5


def test_build_message_uses_given_sequence_and_context() -> None:
    session = PlayerSession(user_name="alice", room_id="alice")
    session.set_context(actor="角色.无名", game="Game1")

    message = session.build_message(NoneEvent(message="a"), sequence_id=9, job_id=3)

    assert message.sequence_id == 9
    assert (message.actor, message.game_name) == ("角色.无名", "Game1")
    assert message.job_id == 3
    assert message.user_name is None  # 默认全房可见


def test_build_message_explicit_values_override_context() -> None:
    session = PlayerSession(user_name="alice", room_id="alice")
    session.set_context(actor="角色.无名", game="Game1")

    message = session.build_message(
        NoneEvent(message="a"),
        sequence_id=1,
        game_name="Game2",
        actor="角色.甲",
        visible_to="alice",
    )

    assert (message.actor, message.game_name) == ("角色.甲", "Game2")
    assert message.user_name == "alice"
