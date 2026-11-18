"""Job 执行记录与 pipeline 观测。

这里把后台 job 的技术过程写成 ``job_events``；它不替代用户级
``PlayerSession`` 历史，只记录一次执行走到哪、哪个 system 失败。
"""

from functools import wraps
from typing import Any, Callable, Optional, Protocol, TypeVar, cast

from loguru import logger
from procrastinate import JobContext

from ..models import JobEvent
from ..pgsql import append_job_event
from ..session.job_context import CurrentJob, reset_current_job, set_current_job
from ..session.room import PlayerRoom


###############################################################################
class JobEventStore(Protocol):
    """job_events 的写入接口；生产实现写 Postgres，测试可替换。"""

    def append(self, event: JobEvent) -> None:
        """追加一条事件。"""


###############################################################################
class DatabaseJobEventStore:
    """生产环境的 job_events 写入实现。"""

    def append(self, event: JobEvent) -> None:
        append_job_event(event)


###############################################################################
class JobRecorder:
    """把一次 job 的执行过程写成事件。"""

    def __init__(
        self,
        job_id: int,
        *,
        action: str = "",
        user_name: str = "",
        store: Optional[JobEventStore] = None,
    ) -> None:
        self.job_id: int = job_id
        self.action: str = action
        self.user_name: str = user_name
        self.store: JobEventStore = store or DatabaseJobEventStore()
        self.current_system: Optional[str] = None

    ###############################################################################
    def record(
        self,
        kind: str,
        *,
        message: str = "",
        system: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> None:
        """写入事件；日志失败不拖垮游戏主流程。"""
        event = JobEvent(
            job_id=self.job_id,
            kind=kind,
            system=system,
            message=message,
            payload=payload or {},
        )
        try:
            self.store.append(event)
        except Exception as exc:  # noqa: BLE001 - 进度日志是旁路
            logger.warning(
                f"job event 写入失败: job_id={self.job_id}, kind={kind}: {exc}"
            )

    ###############################################################################
    def started(self) -> None:
        self.record(
            "job_started",
            message=f"job started: {self.action}",
            payload={"action": self.action, "user_name": self.user_name},
        )

    def succeeded(self) -> None:
        self.record("job_succeeded", message="job succeeded")

    def failed(self, error: BaseException, *, system: Optional[str] = None) -> None:
        self.record(
            "job_failed",
            message=str(error),
            system=system,
            payload={"error_type": type(error).__name__},
        )

    ###############################################################################
    def on_processor_started(self, system: str) -> None:
        self.current_system = system
        self.record("system_started", system=system)

    def on_processor_finished(self, system: str, duration_ms: float) -> None:
        self.record(
            "system_finished",
            system=system,
            payload={"duration_ms": round(duration_ms, 3)},
        )
        if self.current_system == system:
            self.current_system = None

    def on_processor_failed(
        self, system: str, error: BaseException, duration_ms: float
    ) -> None:
        self.current_system = system
        self.record(
            "system_failed",
            system=system,
            message=str(error),
            payload={
                "duration_ms": round(duration_ms, 3),
                "error_type": type(error).__name__,
            },
        )


###############################################################################
class JobRun(CurrentJob):
    """一次 job 的执行上下文：记录事件、绑定房间、失败时恢复世界。"""

    def __init__(
        self,
        job_id: int,
        *,
        action: str = "",
        user_name: str = "",
        store: Optional[JobEventStore] = None,
    ) -> None:
        self.job_id: int = job_id
        self.recorder: JobRecorder = JobRecorder(
            job_id,
            action=action,
            user_name=user_name,
            store=store,
        )
        self._room: Optional[PlayerRoom] = None

    ###############################################################################
    def bind_room(self, room: object) -> None:
        """由 GameServer.acquire 在进入房间事务时调用。"""
        if not isinstance(room, PlayerRoom):
            return
        if self._room is not None:
            return
        self._room = room

    ###############################################################################
    async def __aenter__(self) -> "JobRun":
        self.recorder.started()
        return self

    ###############################################################################
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> bool:
        if exc is None:
            self.recorder.succeeded()
            return False

        self.recorder.failed(exc, system=self.recorder.current_system)

        return False

    ###############################################################################
    # CurrentJob / PipelineObserver 接口
    ###############################################################################
    def on_processor_started(self, system: str) -> None:
        self.recorder.on_processor_started(system)

    def on_processor_finished(self, system: str, duration_ms: float) -> None:
        self.recorder.on_processor_finished(system, duration_ms)

    def on_processor_failed(
        self, system: str, error: BaseException, duration_ms: float
    ) -> None:
        self.recorder.on_processor_failed(system, error, duration_ms)


###############################################################################
F = TypeVar("F", bound=Callable[..., Any])


def job_task(action: str) -> Callable[[F], F]:
    """把 Procrastinate task 包装成带 job 事件记录的执行单元。

    用法：放在 ``@procrastinate_app.task(...)`` 内层。
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(context: JobContext, *args: Any, **kwargs: Any) -> Any:
            job_id = context.job.id
            assert job_id is not None, "运行中的 job 必然有 job id"
            user_name = str(kwargs.get("user_name", ""))
            job = JobRun(job_id, action=action, user_name=user_name)
            token = set_current_job(job)
            try:
                async with job:
                    return await func(context, *args, **kwargs)
            finally:
                reset_current_job(token)

        return cast(F, wrapper)

    return decorator
