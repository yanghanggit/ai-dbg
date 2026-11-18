"""Job 执行事件持久化模型。"""

from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class JobEventDB(Base):
    """一次 job 执行过程中的事件日志；状态本身仍由 Procrastinate 管理。"""

    __tablename__ = "job_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    system: Mapped[str | None] = mapped_column(String(128), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    #: 结构化载荷；用 JSONB 以便直接按内部字段做 SQL 查询（与 game_snapshots 一致）。
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
