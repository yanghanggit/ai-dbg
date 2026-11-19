"""会话历史的持久化边界与领域事件写入。

``SessionMessageStore`` 是存储接口，``session_store()`` 是唯一注入点。
"""

from typing import List, Optional, Protocol

from ..game.events.sink import DomainEventSink
from ..models import AnyAgentEvent, SessionMessage
from ..pgsql import (
    append_session_message,
    list_session_messages,
    max_session_sequence,
)
from ..session.job_context import current_job_id
from ..session.player_session import PlayerSession
from ..session.room import Room


###############################################################################
class SessionMessageStore(Protocol):
    """局级会话流的存储接口（append-only + 按序号增量读取）。"""

    def latest_sequence(self, room_id: str) -> int:
        """该局已分配的最大序号；没有历史时返回 0。"""

    def append(self, room_id: str, message: SessionMessage) -> None:
        """追加一条历史。"""

    def messages_since(
        self,
        room_id: str,
        after_sequence_id: int,
        *,
        viewer: Optional[str] = None,
        limit: int = 500,
    ) -> List[SessionMessage]:
        """按序号升序读取 ``after_sequence_id`` 之后的若干条。"""


###############################################################################
class DatabaseSessionMessageStore:
    """生产实现：写 ``session_messages`` 表。"""

    def latest_sequence(self, room_id: str) -> int:
        return max_session_sequence(room_id)

    def append(self, room_id: str, message: SessionMessage) -> None:
        append_session_message(room_id, message)

    def messages_since(
        self,
        room_id: str,
        after_sequence_id: int,
        *,
        viewer: Optional[str] = None,
        limit: int = 500,
    ) -> List[SessionMessage]:
        return list_session_messages(
            room_id,
            after_sequence_id=after_sequence_id,
            limit=limit,
            viewer=viewer,
        )


###############################################################################
def session_store() -> SessionMessageStore:
    """存储入口：生产写 Postgres；测试替换这一层就不必访问数据库。"""
    return DatabaseSessionMessageStore()


###############################################################################
def open_session(
    room_id: str,
    user_name: str,
    *,
    store: Optional[SessionMessageStore] = None,
) -> PlayerSession:
    """构造某席位在局级流上的游标（默认停在流头，即"加入即已读"）。"""
    message_store = store or session_store()
    return PlayerSession(
        user_name=user_name,
        room_id=room_id,
        event_sequence=message_store.latest_sequence(room_id),
    )


###############################################################################
class SessionEventSink(DomainEventSink):
    """把领域事件追加到局级会话流；序号由房间分配，只推进写者自己的游标。"""

    def __init__(
        self,
        room: Room,
        session: PlayerSession,
        *,
        store: Optional[SessionMessageStore] = None,
    ) -> None:
        self._room = room
        self._session = session
        self._store = store or session_store()
        self._room.seed_event_sequence(self._store.latest_sequence(self._room.room_id))

    def publish(self, agent_event: AnyAgentEvent) -> None:
        sequence_id = self._room.next_event_sequence()
        message = self._session.build_message(
            agent_event,
            sequence_id=sequence_id,
            job_id=current_job_id(),
        )
        self._store.append(self._room.room_id, message)
        self._session.event_sequence = sequence_id
