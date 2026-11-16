"""当前后台 job 的上下文。

job 执行期间用 contextvar 暴露当前 job；领域事件 sink 与 pipeline observer
据此把事件关联到具体 job，而不需要把 job 注入 DBGGame。
"""

from contextvars import ContextVar, Token
from typing import Optional, Protocol


###############################################################################
class CurrentJob(Protocol):
    """当前 job 需要暴露给其他层的最小接口。"""

    job_id: int

    def bind_room(self, room: object) -> None:
        """绑定正在处理的房间；由 GameServer.acquire 调用。"""

    def on_processor_started(self, system: str) -> None:
        """pipeline 开始执行某个 system。"""

    def on_processor_finished(self, system: str, duration_ms: float) -> None:
        """pipeline 完成某个 system。"""

    def on_processor_failed(
        self, system: str, error: BaseException, duration_ms: float
    ) -> None:
        """pipeline 中某个 system 抛异常。"""


###############################################################################
_current_job: ContextVar[Optional[CurrentJob]] = ContextVar("current_job", default=None)


def get_current_job() -> Optional[CurrentJob]:
    """返回当前异步上下文中的 job。"""
    return _current_job.get()


def set_current_job(job: CurrentJob) -> Token[Optional[CurrentJob]]:
    """设置当前 job，返回用于恢复的 token。"""
    return _current_job.set(job)


def reset_current_job(token: Token[Optional[CurrentJob]]) -> None:
    """恢复进入 job 前的上下文。"""
    _current_job.reset(token)


def current_job_id() -> Optional[int]:
    """返回当前 job id；没有 job 时返回 None。"""
    job = get_current_job()
    return job.job_id if job is not None else None
