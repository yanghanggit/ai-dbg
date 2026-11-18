"""用户会话历史持久化模型（append-only）。

一行 = 一条 ``SessionMessage``。``sequence_id`` 按用户全局递增，与内存里的
``PlayerSession`` 游标一致；``(user_name, sequence_id)`` 唯一，保证重放时不会
出现重复序号。
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SessionMessageDB(Base):
    """用户级会话中的一条历史事件；只追加，不更新。"""

    __tablename__ = "session_messages"
    __table_args__ = (
        UniqueConstraint(
            "user_name", "sequence_id", name="uq_session_messages_user_sequence"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    #: 用户级递增序号（增量读取的游标，等于 PlayerSession 分配的值）
    sequence_id: Mapped[int] = mapped_column(Integer, nullable=False)

    #: 产生该事件时的 job；与 job_events 通过它关联
    job_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    game_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    actor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    #: AnyAgentEvent 的 JSON 表示（判别字段是 type）
    agent_event: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
