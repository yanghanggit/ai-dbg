"""会话历史持久化的往返测试（需要数据库）。

只验证「按局追加 → 按序号增量读 → 可见性过滤 → 游标」这条存储契约，不涉及
HTTP 与 pipeline。用随机房间号隔离，结束后清理自己写入的行。
"""

import uuid
from typing import Iterator

import pytest
from sqlalchemy import text

from ai_srpg.gameplay.session_history import (
    DatabaseSessionMessageStore,
    open_session,
)
from ai_srpg.models import NoneEvent, SessionMessage
from ai_srpg.pgsql import pgsql_ensure_database_tables
from ai_srpg.pgsql.client import engine
from ai_srpg.pgsql.session_message_operations import (
    append_session_message,
    list_session_messages,
    max_session_sequence,
)


###############################################################################
@pytest.fixture(scope="module", autouse=True)
def _tables() -> None:
    pgsql_ensure_database_tables()


@pytest.fixture
def room_id() -> Iterator[str]:
    name = f"test-session-{uuid.uuid4().hex[:8]}"
    yield name
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM session_messages WHERE room_id = :name"),
            {"name": name},
        )


def _message(
    sequence_id: int, content: str, *, visible_to: str | None = None
) -> SessionMessage:
    return SessionMessage(
        agent_event=NoneEvent(message=content),
        sequence_id=sequence_id,
        job_id=sequence_id * 10,
        game_name="Game1",
        actor="角色.无名",
        user_name=visible_to,
    )


###############################################################################
def test_append_and_read_incrementally(room_id: str) -> None:
    append_session_message(room_id, _message(1, "第一句"))
    append_session_message(room_id, _message(2, "第二句"))

    assert [m.sequence_id for m in list_session_messages(room_id)] == [1, 2]
    assert [
        m.sequence_id for m in list_session_messages(room_id, after_sequence_id=1)
    ] == [2]
    assert [m.sequence_id for m in list_session_messages(room_id, limit=1)] == [1]


def test_agent_event_round_trips_through_jsonb(room_id: str) -> None:
    append_session_message(room_id, _message(1, "带事件的消息"))

    restored = list_session_messages(room_id)[0]

    assert restored.agent_event is not None
    assert restored.agent_event.message == "带事件的消息"
    assert restored.agent_event.type == "none"
    assert (restored.job_id, restored.game_name, restored.actor) == (
        10,
        "Game1",
        "角色.无名",
    )


def test_max_sequence_and_store_cursor(room_id: str) -> None:
    assert max_session_sequence(room_id) == 0

    store = DatabaseSessionMessageStore()
    store.append(room_id, _message(1, "a"))
    store.append(room_id, _message(2, "b"))

    assert store.latest_sequence(room_id) == 2
    # 席位加入时游标停在流头（"加入即已读"）
    assert open_session(room_id, "alice", store=store).event_sequence == 2


def test_messages_are_isolated_per_room(room_id: str) -> None:
    other = f"{room_id}-other"
    append_session_message(room_id, _message(1, "mine"))
    append_session_message(other, _message(1, "theirs"))

    try:
        restored = list_session_messages(room_id)
        contents = [m.agent_event.message for m in restored if m.agent_event]
        assert contents == ["mine"]
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM session_messages WHERE room_id = :name"),
                {"name": other},
            )


def test_visibility_filters_other_players_events(room_id: str) -> None:
    """同一局一条流：全房可见的事件人人能读，专属事件只有本人能读。"""
    append_session_message(room_id, _message(1, "全房"))
    append_session_message(room_id, _message(2, "只给 alice", visible_to="alice"))
    append_session_message(room_id, _message(3, "只给 bob", visible_to="bob"))

    def contents(viewer: str) -> list[str]:
        return [
            m.agent_event.message
            for m in list_session_messages(room_id, viewer=viewer)
            if m.agent_event is not None
        ]

    assert contents("alice") == ["全房", "只给 alice"]
    assert contents("bob") == ["全房", "只给 bob"]
    assert [m.sequence_id for m in list_session_messages(room_id)] == [1, 2, 3]
