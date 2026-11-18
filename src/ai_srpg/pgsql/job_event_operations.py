"""job_events 的读写操作。"""

from typing import List, Optional

from ..models import JobEvent
from .client import SessionLocal
from .job_event import JobEventDB


def _to_model(row: JobEventDB) -> JobEvent:
    return JobEvent(
        id=row.id,
        job_id=row.job_id,
        kind=row.kind,
        system=row.system,
        message=row.message,
        payload=row.payload,
        created_at=row.created_at,
    )


def append_job_event(event: JobEvent) -> JobEvent:
    """追加一条 job 事件。"""
    db = SessionLocal()
    try:
        row = JobEventDB(
            job_id=event.job_id,
            kind=event.kind,
            system=event.system,
            message=event.message,
            payload=event.payload,
            created_at=event.created_at,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _to_model(row)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def list_job_events(
    job_id: int, *, after_id: int = 0, limit: int = 500
) -> List[JobEvent]:
    """按 id 升序读取 job 事件；``after_id`` 用于增量轮询。"""
    db = SessionLocal()
    try:
        rows = (
            db.query(JobEventDB)
            .filter(JobEventDB.job_id == job_id, JobEventDB.id > after_id)
            .order_by(JobEventDB.id.asc())
            .limit(limit)
            .all()
        )
        return [_to_model(row) for row in rows]
    finally:
        db.close()


def get_job_error(job_id: int) -> Optional[str]:
    """返回 job 的最终失败信息（若存在）。"""
    db = SessionLocal()
    try:
        row = (
            db.query(JobEventDB)
            .filter(
                JobEventDB.job_id == job_id,
                JobEventDB.kind.in_(("job_failed", "system_failed")),
            )
            .order_by(JobEventDB.id.desc())
            .first()
        )
        return row.message if row is not None else None
    finally:
        db.close()
