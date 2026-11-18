"""把游戏领域事件写入用户会话历史。"""

from typing import Optional

from ..game.events.sink import DomainEventSink
from ..job_context import current_job_id
from ..models import AnyAgentEvent, PlayerSession
from .store import SessionStore


###############################################################################
class PlayerSessionEventSink(DomainEventSink):
    """领域事件 sink 的持久化实现。"""

    def __init__(
        self,
        session: PlayerSession,
        store: SessionStore,
        *,
        job_id: Optional[int] = None,
    ) -> None:
        self._session: PlayerSession = session
        self._store: SessionStore = store
        self._job_id: Optional[int] = job_id

    ###############################################################################
    @property
    def session(self) -> PlayerSession:
        return self._session

    ###############################################################################
    def set_job(self, job_id: Optional[int]) -> None:
        """绑定当前 job；后续事件会带上该 job_id。"""
        self._job_id = job_id

    ###############################################################################
    def publish(self, agent_event: AnyAgentEvent) -> None:
        job_id = self._job_id if self._job_id is not None else current_job_id()
        message = self._session.add_agent_event(
            agent_event,
            job_id=job_id,
        )
        try:
            self._store.append(self._session, message)
        except Exception:
            # 持久化失败时回滚内存追加，避免内存历史与磁盘历史分叉
            self._session.session_messages.pop()
            self._session.event_sequence -= 1
            raise
