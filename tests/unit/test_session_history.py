"""会话历史写入边界：局级存储接口、游标恢复、序号分配与 job 关联。"""

from typing import List, Optional

from ai_srpg.gameplay.session_history import (
    SessionEventSink,
    SessionMessageStore,
    open_session,
)
from ai_srpg.models import NoneEvent, SessionMessage
from ai_srpg.session.job_context import reset_current_job, set_current_job
from ai_srpg.session.room import Room


###############################################################################
class _FakeStore:
    """内存版存储：一局一条流，按序号返回历史并按可见性过滤。"""

    def __init__(self, messages: List[SessionMessage] | None = None) -> None:
        self.messages: List[SessionMessage] = list(messages or [])
        self.appended: List[SessionMessage] = []

    def latest_sequence(self, room_id: str) -> int:
        return max((m.sequence_id for m in self.messages), default=0)

    def append(self, room_id: str, message: SessionMessage) -> None:
        self.appended.append(message)
        self.messages.append(message)

    def messages_since(
        self,
        room_id: str,
        after_sequence_id: int,
        *,
        viewer: Optional[str] = None,
        limit: int = 500,
    ) -> List[SessionMessage]:
        visible = [
            m
            for m in self.messages
            if m.sequence_id > after_sequence_id
            and (viewer is None or m.user_name in (None, viewer))
        ]
        return visible[:limit]


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


def _room(owner: str = "alice") -> Room:
    return Room(room_id=owner, owner=owner)


###############################################################################
def test_open_session_starts_at_stream_head() -> None:
    store = _FakeStore([SessionMessage(sequence_id=7, agent_event=None)])

    session = open_session("alice", "alice", store=store)

    assert (session.user_name, session.room_id) == ("alice", "alice")
    assert session.event_sequence == 7


def test_sink_allocates_room_sequence_and_advances_writer_cursor() -> None:
    store = _FakeStore([SessionMessage(sequence_id=7, agent_event=None)])
    room = _room()
    session = open_session("alice", "alice", store=store)
    sink = SessionEventSink(room, session, store=store)

    token = set_current_job(_FakeJob(job_id=42))
    try:
        sink.publish(NoneEvent(message="hello"))
    finally:
        reset_current_job(token)

    assert len(store.appended) == 1
    message = store.appended[0]
    assert message.sequence_id == 8
    assert message.job_id == 42
    assert message.user_name is None
    assert session.event_sequence == 8


def test_second_seat_keeps_its_own_cursor() -> None:
    """局级流只有一条：事件写一次，别的席位游标不跟着跳。"""
    store = _FakeStore()
    room = _room()
    room.join("bob")
    alice = open_session("alice", "alice", store=store)
    bob = open_session("alice", "bob", store=store)
    room.attach_session(alice)
    room.attach_session(bob)

    sink = SessionEventSink(room, alice, store=store)
    sink.publish(NoneEvent(message="hello"))

    assert alice.event_sequence == 1
    assert bob.event_sequence == 0
    assert len(store.appended) == 1


def test_sink_without_job_context_writes_null_job_id() -> None:
    store = _FakeStore()
    sink = SessionEventSink(
        _room(), open_session("alice", "alice", store=store), store=store
    )

    sink.publish(NoneEvent(message="hello"))

    assert store.appended[0].job_id is None


def test_store_implements_protocol() -> None:
    """静态检查：内存实现与生产实现满足同一接口。"""

    def _accept(store: SessionMessageStore) -> int:
        return store.latest_sequence("alice")

    assert _accept(_FakeStore()) == 0
