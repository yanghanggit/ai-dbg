"""session_messages 的读写：只追加与按序号读取；读取可按 ``viewer`` 过滤可见性。"""

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
        user_name=row.user_name,
        created_at=row.created_at,
    )


###############################################################################
def append_session_message(room_id: str, message: SessionMessage) -> None:
    """追加一条会话消息；序号冲突会由唯一约束抛出（不应发生）。"""
    db = SessionLocal()
    try:
        db.add(
            SessionMessageDB(
                room_id=room_id,
                sequence_id=message.sequence_id,
                user_name=message.user_name,
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
    room_id: str,
    *,
    after_sequence_id: int = 0,
    limit: int = 500,
    viewer: Optional[str] = None,
) -> List[SessionMessage]:
    """按序号升序读取某一局的历史；``after_sequence_id`` 用于增量拉取。

    传入 ``viewer`` 时只返回他可见的事件（全房可见 + 专属他的）。
    """
    db = SessionLocal()
    try:
        query = db.query(SessionMessageDB).filter(
            SessionMessageDB.room_id == room_id,
            SessionMessageDB.sequence_id > after_sequence_id,
        )
        if viewer is not None:
            query = query.filter(
                (SessionMessageDB.user_name.is_(None))
                | (SessionMessageDB.user_name == viewer)
            )
        rows = query.order_by(SessionMessageDB.sequence_id.asc()).limit(limit).all()
        return [_to_model(row) for row in rows]
    finally:
        db.close()


###############################################################################
def max_session_sequence(room_id: str) -> int:
    """该局已分配的最大序号；没有历史时返回 0。"""
    db = SessionLocal()
    try:
        row: Optional[int] = (
            db.query(SessionMessageDB.sequence_id)
            .filter(SessionMessageDB.room_id == room_id)
            .order_by(SessionMessageDB.sequence_id.desc())
            .limit(1)
            .scalar()
        )
        return int(row) if row is not None else 0
    finally:
        db.close()
