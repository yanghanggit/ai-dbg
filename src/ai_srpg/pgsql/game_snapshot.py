"""游戏快照持久化模型（append-only 历史）。"""

from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class GameSnapshotDB(Base):
    """一次游戏运行的整块快照；只追加，不更新。

    行按 ``id`` 递增即为时间顺序：最新状态 = 最大 id，回滚 = 读取更早的 id。
    哪个用户/哪局游戏由 ``user_name`` + ``game_name`` 标识。
    """

    __tablename__ = "game_snapshots"
    __table_args__ = (
        Index("ix_game_snapshots_lookup", "user_name", "game_name", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_name: Mapped[str] = mapped_column(String(255), nullable=False)
    game_name: Mapped[str] = mapped_column(String(255), nullable=False)

    #: 与 GameSnapshot.format_version 一致，便于不解包 JSON 就能筛查旧格式。
    format_version: Mapped[int] = mapped_column(Integer, nullable=False)

    #: GameSnapshot.model_dump(mode="json") 的完整内容。
    data: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
