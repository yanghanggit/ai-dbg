from datetime import datetime, timezone
from typing import Optional, final

from pydantic import BaseModel, Field

from .agent_event import AnyAgentEvent


@final
class SessionMessage(BaseModel):
    """局级会话流中的一条历史事件；``user_name`` 是可见者（None = 全房可见）。"""

    agent_event: Optional[AnyAgentEvent] = None
    sequence_id: int = 0
    job_id: Optional[int] = None
    game_name: Optional[str] = None
    actor: Optional[str] = None
    user_name: Optional[str] = None  # 可见者；None = 全房可见
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


###############################################################################
__all__ = ["SessionMessage"]
