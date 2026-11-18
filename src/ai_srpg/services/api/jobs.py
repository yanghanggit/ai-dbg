"""Job 状态与执行事件查询接口。

队列状态由 Procrastinate 实时提供；执行过程与失败详情来自 ``job_events``。
"""

import asyncio
import json
from typing import Annotated, AsyncGenerator, Final, List

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from loguru import logger
from procrastinate.exceptions import NoResult
from procrastinate.jobs import Status as ProcrastinateJobStatus

from ...pgsql import get_job_error, list_job_events, procrastinate_app
from .schemas import (
    JobDetail,
    JobEventsResponse,
    JobSnapshot,
    JobStatusListResponse,
)

################################################################################################################
jobs_api_router = APIRouter()

TERMINAL_STATUSES: Final = frozenset(
    {
        ProcrastinateJobStatus.SUCCEEDED,
        ProcrastinateJobStatus.FAILED,
        ProcrastinateJobStatus.CANCELLED,
        ProcrastinateJobStatus.ABORTED,
    }
)


###############################################################################
async def get_job_snapshot(job_id: int) -> JobSnapshot:
    """查询指定 job 的当前状态；job 不存在时由 Procrastinate 抛出 NoResult。"""
    job_status = await procrastinate_app.job_manager.get_job_status_async(job_id)
    error = (
        get_job_error(job_id) if job_status == ProcrastinateJobStatus.FAILED else None
    )
    return JobSnapshot(job_id=job_id, status=job_status, error=error)


###############################################################################
@jobs_api_router.get(path="/api/jobs/v1/status", response_model=JobStatusListResponse)
async def get_jobs_status(
    job_ids: Annotated[List[int], Query(alias="job_ids")],
) -> JobStatusListResponse:
    """批量查询 job 状态；不存在的 job_id 会被跳过。"""
    logger.info(f"🔍 批量查询 job 状态: job_ids={job_ids}")
    jobs: List[JobSnapshot] = []
    for job_id in job_ids:
        try:
            snapshot = await get_job_snapshot(job_id)
        except NoResult:
            logger.warning(f"⚠️ 查询的 job 不存在: job_id={job_id}")
            continue
        logger.info(f"🔍 查询到 job 状态: job_id={job_id}, status={snapshot.status}")
        jobs.append(snapshot)
    return JobStatusListResponse(jobs=jobs)


###############################################################################
@jobs_api_router.get(
    path="/api/jobs/v1/{job_id}/events", response_model=JobEventsResponse
)
async def get_job_events(
    job_id: int,
    after_id: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=2000),
) -> JobEventsResponse:
    """增量读取 job 的执行事件。"""
    try:
        await procrastinate_app.job_manager.get_job_status_async(job_id)
    except NoResult as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="job not found",
        ) from exc
    return JobEventsResponse(
        job_id=job_id,
        events=list_job_events(job_id, after_id=after_id, limit=limit),
    )


###############################################################################
@jobs_api_router.get(path="/api/jobs/v1/{job_id}", response_model=JobDetail)
async def get_job_detail(job_id: int) -> JobDetail:
    """查询单个 job 的状态与完整执行事件。"""
    try:
        snapshot = await get_job_snapshot(job_id)
    except NoResult as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="job not found",
        ) from exc
    return JobDetail(
        job_id=snapshot.job_id,
        status=snapshot.status,
        error=snapshot.error,
        events=list_job_events(job_id),
    )


###############################################################################
@jobs_api_router.get(path="/api/jobs/v1/watch/{job_id}")
async def watch_job(
    job_id: int,
    timeout_seconds: int = Query(default=120, ge=1, le=600),
    interval: float = Query(default=0.3, ge=0.1, le=5.0),
) -> StreamingResponse:
    """SSE 端点：推送 job 状态直至终态或超时。"""

    async def event_generator(poll_interval: float) -> AsyncGenerator[str, None]:
        elapsed = 0.0
        while elapsed < timeout_seconds:
            try:
                snapshot = await get_job_snapshot(job_id)
            except NoResult:
                payload = json.dumps({"error": "job_not_found", "job_id": job_id})
                yield f"data: {payload}\n\n"
                logger.warning(f"watch_job: job 不存在 job_id={job_id}")
                return

            yield f"data: {snapshot.model_dump_json()}\n\n"
            if snapshot.status in TERMINAL_STATUSES:
                logger.info(
                    f"watch_job: job 终态 job_id={job_id} status={snapshot.status}"
                )
                return

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        payload = json.dumps({"error": "timeout", "job_id": job_id})
        yield f"data: {payload}\n\n"
        logger.warning(f"watch_job: 超时 job_id={job_id}")

    return StreamingResponse(event_generator(interval), media_type="text/event-stream")
