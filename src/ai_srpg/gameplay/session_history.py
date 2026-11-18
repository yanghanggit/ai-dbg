"""会话历史的持久化边界与领域事件写入。

数据库是会话历史的唯一真相：``PlayerSession`` 只保存序号游标与当前上下文，
历史消息按需增量读取。领域事件经 ``SessionEventSink`` 追加进来——它与 job 日志
的区别是「玩家可见的领域历史」，通过 ``job_id`` 与执行过程关联而不合并。

``SessionMessageStore`` 是存储接口，生产实现写 Postgres；测试可替换。
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


###############################################################################
class SessionMessageStore(Protocol):
    """会话历史的存储接口（append-only + 按序号增量读取）。"""

    def latest_sequence(self, user_name: str) -> int:
        """该用户已分配的最大序号；没有历史时返回 0。"""

    def append(self, user_name: str, message: SessionMessage) -> None:
        """追加一条历史。"""

    def messages_since(
        self, user_name: str, after_sequence_id: int, *, limit: int = 500
    ) -> List[SessionMessage]:
        """按序号升序读取 ``after_sequence_id`` 之后的若干条。"""


###############################################################################
class DatabaseSessionMessageStore:
    """生产实现：写 ``session_messages`` 表。"""

    def latest_sequence(self, user_name: str) -> int:
        return max_session_sequence(user_name)

    def append(self, user_name: str, message: SessionMessage) -> None:
        append_session_message(user_name, message)

    def messages_since(
        self, user_name: str, after_sequence_id: int, *, limit: int = 500
    ) -> List[SessionMessage]:
        return list_session_messages(
            user_name, after_sequence_id=after_sequence_id, limit=limit
        )


###############################################################################
def open_session(
    user_name: str, *, store: Optional[SessionMessageStore] = None
) -> PlayerSession:
    """从存储恢复会话（只需游标；历史按需增量读取）。"""
    session_store = store or DatabaseSessionMessageStore()
    return PlayerSession(
        name=user_name,
        event_sequence=session_store.latest_sequence(user_name),
    )


###############################################################################
class SessionEventSink(DomainEventSink):
    """把游戏领域事件追加到用户会话并落盘。

    在一次 pass 内发布的事件会自动带上当前 ``job_id``；游戏与角色取会话的
    当前上下文（由开局时写入）。
    """

    def __init__(
        self, session: PlayerSession, *, store: Optional[SessionMessageStore] = None
    ) -> None:
        self._session = session
        self._store = store or DatabaseSessionMessageStore()

    def publish(self, agent_event: AnyAgentEvent) -> None:
        message = self._session.add_agent_event(
            agent_event,
            job_id=current_job_id(),
        )
        self._store.append(self._session.name, message)
