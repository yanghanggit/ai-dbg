from datetime import datetime, timezone
from typing import Optional, final

from pydantic import BaseModel, Field

from .agent_event import AnyAgentEvent


@final
class SessionMessage(BaseModel):
    """用户会话中的一条历史事件。

    ``sequence_id`` 按用户全局递增；``job_id`` / ``game_name`` / ``actor`` 用于把
    跨游戏的上帝视角历史关联回具体执行与局面。
    """

    agent_event: Optional[AnyAgentEvent] = None
    sequence_id: int = 0
    job_id: Optional[int] = None
    game_name: Optional[str] = None
    actor: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
