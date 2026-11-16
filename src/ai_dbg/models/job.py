"""Job 相关模型。

命名约定（全项目统一）：

- ``Job``：应用层的执行单元（进入队列、可追踪状态的一次工作）；
- ``job_id``：该执行实例在 Procrastinate 中的标识，是本项目唯一的 job 标识字段。

因此模块 / 模型 / 接口统一用 ``job`` 命名；Procrastinate 的 ``task`` 只表示
框架里的注册模板，不进入业务词汇。
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, final

from procrastinate.jobs import Status as ProcrastinateJobStatus
from pydantic import BaseModel, Field


@final
class JobEvent(BaseModel):
    """一次 job 执行过程中的结构化事件。"""

    id: int = 0
    job_id: int
    kind: str
    system: Optional[str] = None
    message: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@final
class JobSnapshot(BaseModel):
    """由 Procrastinate job 状态与 job_events 推导出的 job 快照。"""

    job_id: int
    status: ProcrastinateJobStatus
    error: Optional[str] = None


@final
class JobDetail(BaseModel):
    """单个 job 的状态 + 执行事件。"""

    job_id: int
    status: ProcrastinateJobStatus
    error: Optional[str] = None
    events: List[JobEvent] = Field(default_factory=list)
