"""局级会话流（append-only）：一行一条，``(room_id, sequence_id)`` 唯一。"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SessionMessageDB(Base):
    """一局游戏会话流中的一条历史事件；只追加，不更新。"""

    __tablename__ = "session_messages"
    __table_args__ = (
        UniqueConstraint(
            "room_id", "sequence_id", name="uq_session_messages_room_sequence"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    #: 所属局（房间）；会话流按它划分
    room_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    #: 局内递增序号（增量读取的游标，由 Room 分配）
    sequence_id: Mapped[int] = mapped_column(Integer, nullable=False)

    #: 可见者：NULL = 全房可见；非 NULL = 只对该玩家可见
    user_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )

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
