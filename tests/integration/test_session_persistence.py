"""会话历史持久化的往返测试（需要数据库）。

只验证「追加 → 按序号增量读 → 游标」这条存储契约，不涉及 HTTP 与 pipeline。
用随机用户名隔离，结束后清理自己写入的行。
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
def user_name() -> Iterator[str]:
    name = f"test-session-{uuid.uuid4().hex[:8]}"
    yield name
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM session_messages WHERE user_name = :name"),
            {"name": name},
        )


def _message(sequence_id: int, content: str) -> SessionMessage:
    return SessionMessage(
        agent_event=NoneEvent(message=content),
        sequence_id=sequence_id,
        job_id=sequence_id * 10,
        game_name="Game1",
        actor="角色.无名",
    )


###############################################################################
def test_append_and_read_incrementally(user_name: str) -> None:
    append_session_message(user_name, _message(1, "第一句"))
    append_session_message(user_name, _message(2, "第二句"))

    assert [m.sequence_id for m in list_session_messages(user_name)] == [1, 2]
    assert [
        m.sequence_id for m in list_session_messages(user_name, after_sequence_id=1)
    ] == [2]
    assert [m.sequence_id for m in list_session_messages(user_name, limit=1)] == [1]


def test_agent_event_round_trips_through_jsonb(user_name: str) -> None:
    append_session_message(user_name, _message(1, "带事件的消息"))

    restored = list_session_messages(user_name)[0]

    assert restored.agent_event is not None
    assert restored.agent_event.message == "带事件的消息"
    assert restored.agent_event.type == "none"
    assert (restored.job_id, restored.game_name, restored.actor) == (
        10,
        "Game1",
        "角色.无名",
    )


def test_max_sequence_and_store_cursor(user_name: str) -> None:
    assert max_session_sequence(user_name) == 0

    store = DatabaseSessionMessageStore()
    store.append(user_name, _message(1, "a"))
    store.append(user_name, _message(2, "b"))

    assert store.latest_sequence(user_name) == 2
    assert open_session(user_name, store=store).event_sequence == 2


def test_messages_are_isolated_per_user(user_name: str) -> None:
    other = f"{user_name}-other"
    append_session_message(user_name, _message(1, "mine"))
    append_session_message(other, _message(1, "theirs"))

    try:
        restored = list_session_messages(user_name)
        contents = [m.agent_event.message for m in restored if m.agent_event]
        assert contents == ["mine"]
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM session_messages WHERE user_name = :name"),
                {"name": other},
            )
