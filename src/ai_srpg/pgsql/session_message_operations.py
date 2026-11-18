"""session_messages 的读写操作。

会话历史是 append-only 的：这里只有追加与按序号读取，没有更新与删除。
「何时追加」由上层（领域事件 sink）决定，本层不做编排。
"""

from typing import List, Optional

from pydantic import TypeAdapter

from ..models import AnyAgentEvent, SessionMessage
from .client import SessionLocal
from .session_message import SessionMessageDB

_AGENT_EVENT_ADAPTER: TypeAdapter[AnyAgentEvent] = TypeAdapter(AnyAgentEvent)


###############################################################################
def _to_model(row: SessionMessageDB) -> SessionMessage:
    return SessionMessage(
        agent_event=(
            _AGENT_EVENT_ADAPTER.validate_python(row.agent_event)
            if row.agent_event is not None
            else None
        ),
        sequence_id=row.sequence_id,
        job_id=row.job_id,
        game_name=row.game_name,
        actor=row.actor,
        created_at=row.created_at,
    )


###############################################################################
def append_session_message(user_name: str, message: SessionMessage) -> None:
    """追加一条会话消息；序号冲突会由唯一约束抛出（不应发生）。"""
    db = SessionLocal()
    try:
        db.add(
            SessionMessageDB(
                user_name=user_name,
                sequence_id=message.sequence_id,
                job_id=message.job_id,
                game_name=message.game_name,
                actor=message.actor,
                agent_event=(
                    message.agent_event.model_dump(mode="json")
                    if message.agent_event is not None
                    else None
                ),
                created_at=message.created_at,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


###############################################################################
def list_session_messages(
    user_name: str, *, after_sequence_id: int = 0, limit: int = 500
) -> List[SessionMessage]:
    """按序号升序读取某用户的历史；``after_sequence_id`` 用于增量拉取。"""
    db = SessionLocal()
    try:
        rows = (
            db.query(SessionMessageDB)
            .filter(
                SessionMessageDB.user_name == user_name,
                SessionMessageDB.sequence_id > after_sequence_id,
            )
            .order_by(SessionMessageDB.sequence_id.asc())
            .limit(limit)
            .all()
        )
        return [_to_model(row) for row in rows]
    finally:
        db.close()


###############################################################################
def max_session_sequence(user_name: str) -> int:
    """该用户已分配的最大序号；没有历史时返回 0。"""
    db = SessionLocal()
    try:
        row: Optional[int] = (
            db.query(SessionMessageDB.sequence_id)
            .filter(SessionMessageDB.user_name == user_name)
            .order_by(SessionMessageDB.sequence_id.desc())
            .limit(1)
            .scalar()
        )
        return int(row) if row is not None else 0
    finally:
        db.close()
