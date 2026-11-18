"""会话历史写入边界：存储接口、游标恢复与 job 关联。"""

from typing import List

from ai_srpg.gameplay.session_history import (
    SessionEventSink,
    SessionMessageStore,
    open_session,
)
from ai_srpg.models import NoneEvent, SessionMessage
from ai_srpg.session.job_context import reset_current_job, set_current_job
from ai_srpg.session.player_session import PlayerSession


###############################################################################
class _FakeStore:
    """内存版存储：只记录追加，按序号返回历史。"""

    def __init__(self, messages: List[SessionMessage] | None = None) -> None:
        self.messages: List[SessionMessage] = list(messages or [])
        self.appended: List[SessionMessage] = []

    def latest_sequence(self, user_name: str) -> int:
        return max((m.sequence_id for m in self.messages), default=0)

    def append(self, user_name: str, message: SessionMessage) -> None:
        self.appended.append(message)
        self.messages.append(message)

    def messages_since(
        self, user_name: str, after_sequence_id: int, *, limit: int = 500
    ) -> List[SessionMessage]:
        return [m for m in self.messages if m.sequence_id > after_sequence_id][:limit]


class _FakeJob:
    """满足 CurrentJob 协议的最小实现。"""

    def __init__(self, job_id: int) -> None:
        self.job_id: int = job_id

    def bind_room(self, room: object) -> None:
        return None

    def on_processor_started(self, system: str) -> None:
        return None

    def on_processor_finished(self, system: str, duration_ms: float) -> None:
        return None

    def on_processor_failed(
        self, system: str, error: BaseException, duration_ms: float
    ) -> None:
        return None


###############################################################################
def test_open_session_restores_cursor_from_store() -> None:
    store = _FakeStore([SessionMessage(sequence_id=7, agent_event=None)])

    session = open_session("alice", store=store)

    assert session.name == "alice"
    assert session.event_sequence == 7


def test_sink_appends_message_with_current_job_id() -> None:
    store = _FakeStore()
    session = PlayerSession(name="alice", event_sequence=3)
    sink = SessionEventSink(session, store=store)

    token = set_current_job(_FakeJob(job_id=42))
    try:
        sink.publish(NoneEvent(message="hello"))
    finally:
        reset_current_job(token)

    assert len(store.appended) == 1
    message = store.appended[0]
    assert message.sequence_id == 4
    assert message.job_id == 42
    assert message.agent_event is not None


def test_sink_without_job_context_writes_null_job_id() -> None:
    store = _FakeStore()
    sink = SessionEventSink(PlayerSession(name="alice"), store=store)

    sink.publish(NoneEvent(message="hello"))

    assert store.appended[0].job_id is None


def test_store_implements_protocol() -> None:
    """静态检查：内存实现与生产实现满足同一接口。"""

    def _accept(store: SessionMessageStore) -> int:
        return store.latest_sequence("alice")

    assert _accept(_FakeStore()) == 0
