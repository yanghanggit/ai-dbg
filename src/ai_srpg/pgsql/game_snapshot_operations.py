"""game_snapshots 的读写操作。

只做「整块追加」与「按 id 读取」；何时保存、保存后如何回滚由上层编排决定。
"""

from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import GameSnapshot, GameSnapshotInfo, GameSummary
from .client import SessionLocal
from .game_snapshot import GameSnapshotDB


###############################################################################
def append_game_snapshot(
    room_id: str,
    snapshot: GameSnapshot,
    *,
    session: Optional[Session] = None,
) -> int:
    """追加一条快照并返回 id（新增记录即最新状态）。

    传入 ``session`` 时只 flush 不提交，便于与 job 事件共用一个事务。
    """
    row = GameSnapshotDB(
        room_id=room_id,
        game_name=snapshot.game,
        format_version=snapshot.format_version,
        data=snapshot.model_dump(mode="json"),
    )

    if session is not None:
        session.add(row)
        session.flush()
        return row.id

    db = SessionLocal()
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


###############################################################################
def load_latest_game_snapshot(room_id: str, game_name: str) -> Optional[GameSnapshot]:
    """读某一局的最新快照。"""
    db = SessionLocal()
    try:
        row = (
            db.query(GameSnapshotDB)
            .filter(
                GameSnapshotDB.room_id == room_id,
                GameSnapshotDB.game_name == game_name,
            )
            .order_by(GameSnapshotDB.id.desc())
            .first()
        )
        return _to_snapshot(row)
    finally:
        db.close()


###############################################################################
def load_game_snapshot(
    snapshot_id: int,
    *,
    room_id: Optional[str] = None,
    game_name: Optional[str] = None,
) -> Optional[GameSnapshot]:
    """按 id 读取指定快照（可附带房间/游戏归属过滤）。"""
    db = SessionLocal()
    try:
        query = db.query(GameSnapshotDB).filter(GameSnapshotDB.id == snapshot_id)
        if room_id is not None:
            query = query.filter(GameSnapshotDB.room_id == room_id)
        if game_name is not None:
            query = query.filter(GameSnapshotDB.game_name == game_name)
        return _to_snapshot(query.first())
    finally:
        db.close()


###############################################################################
def list_game_snapshot_ids(
    room_id: str, game_name: str, *, limit: int = 50
) -> List[int]:
    """按时间倒序列出快照 id，供选择回滚点。"""
    db = SessionLocal()
    try:
        rows = (
            db.query(GameSnapshotDB.id)
            .filter(
                GameSnapshotDB.room_id == room_id,
                GameSnapshotDB.game_name == game_name,
            )
            .order_by(GameSnapshotDB.id.desc())
            .limit(limit)
            .all()
        )
        return [row.id for row in rows]
    finally:
        db.close()


###############################################################################
def list_game_snapshots(
    room_id: str, game_name: str, *, limit: int = 20
) -> List[GameSnapshotInfo]:
    """按时间倒序列出快照元数据，供 CLI 观察历史。"""
    db = SessionLocal()
    try:
        rows = (
            db.query(GameSnapshotDB)
            .filter(
                GameSnapshotDB.room_id == room_id,
                GameSnapshotDB.game_name == game_name,
            )
            .order_by(GameSnapshotDB.id.desc())
            .limit(limit)
            .all()
        )
        result: List[GameSnapshotInfo] = []
        for row in rows:
            snapshot = GameSnapshot.model_validate(row.data)
            result.append(
                GameSnapshotInfo(
                    id=row.id,
                    game_name=row.game_name,
                    format_version=row.format_version,
                    created_at=row.created_at,
                    entity_count=len(snapshot.ecs.entities),
                    memory_count=len(snapshot.memory.memories),
                )
            )
        return result
    finally:
        db.close()


###############################################################################
def list_game_summaries(room_id: str) -> List[GameSummary]:
    """列出房间（用户）下的所有对局，按最近更新倒序。"""
    db = SessionLocal()
    try:
        rows = (
            db.query(
                GameSnapshotDB.game_name,
                func.max(GameSnapshotDB.id),
                func.count(GameSnapshotDB.id),
                func.max(GameSnapshotDB.created_at),
            )
            .filter(GameSnapshotDB.room_id == room_id)
            .group_by(GameSnapshotDB.game_name)
            .all()
        )
        latest_ids = [row[1] for row in rows]
        latest_rows = {
            row.game_name: row
            for row in db.query(GameSnapshotDB)
            .filter(GameSnapshotDB.id.in_(latest_ids))
            .all()
        }
        summaries: List[GameSummary] = []
        for game_name, latest_id, count, updated_at in rows:
            snapshot = GameSnapshot.model_validate(latest_rows[game_name].data)
            summaries.append(
                GameSummary(
                    game_name=game_name,
                    latest_snapshot_id=latest_id,
                    snapshot_count=count,
                    updated_at=updated_at,
                    entity_count=len(snapshot.ecs.entities),
                )
            )
        return sorted(summaries, key=lambda item: item.updated_at, reverse=True)
    finally:
        db.close()


###############################################################################
def _to_snapshot(row: Optional[GameSnapshotDB]) -> Optional[GameSnapshot]:
    if row is None:
        return None
    return GameSnapshot.model_validate(row.data)
