"""HTTP 传输契约：只做序列化与 OpenAPI 描述，不含领域行为、不参与持久化。"""

from datetime import datetime
from typing import List, Optional, final

from procrastinate.jobs import Status as ProcrastinateJobStatus
from pydantic import BaseModel, Field

from ...entitas import ContextData
from ...models import GameSnapshotInfo, JobEvent, SessionMessage

################################################################################################################
# 组件 / 实体


################################################################################################################
@final
class ComponentNamesResponse(BaseModel):
    """已注册的 ECS 组件类名清单。"""

    names: List[str]


################################################################################################################
@final
class EntitiesDetailsResponse(BaseModel):
    """一组实体的序列化结果。"""

    entities: ContextData


################################################################################################################
# 房间 / 游戏


################################################################################################################
@final
class SeatResponse(BaseModel):
    """房间里的一个席位：谁在玩、控制哪个角色（未分配角色时为 ``None``）。"""

    user_name: str
    actor: Optional[str] = None


################################################################################################################
@final
class RoomStateResponse(BaseModel):
    """房间当前状态。

    ``user_name`` 是发起请求的身份，``room_id`` / ``owner`` / ``seats`` 描述这一局；
    ``session_event_sequence`` 是该席位在局级流上的已读游标（可直接用于增量读取）。
    """

    user_name: str
    room_id: str
    owner: str
    game: Optional[str] = None
    session_event_sequence: int = 0
    seats: List[SeatResponse] = Field(default_factory=list)


################################################################################################################
@final
class DispatchJobResponse(BaseModel):
    """已派发的后台 job。"""

    job_id: int


################################################################################################################
@final
class SnapshotListResponse(BaseModel):
    """快照元数据列表（时间倒序）。"""

    snapshots: List[GameSnapshotInfo]


################################################################################################################
# 会话历史


################################################################################################################
@final
class SessionMessageResponse(BaseModel):
    """增量会话消息。"""

    session_messages: List[SessionMessage]


################################################################################################################
# Job


################################################################################################################
@final
class JobSnapshot(BaseModel):
    """由 Procrastinate job 状态与 job_events 推导出的 job 快照。"""

    job_id: int
    status: ProcrastinateJobStatus
    error: Optional[str] = None


################################################################################################################
@final
class JobStatusListResponse(BaseModel):
    """批量 job 状态。"""

    jobs: List[JobSnapshot]


################################################################################################################
@final
class JobEventsResponse(BaseModel):
    """增量 job 事件。"""

    job_id: int
    events: List[JobEvent]


################################################################################################################
@final
class JobDetail(BaseModel):
    """单个 job 的状态 + 执行事件。"""

    job_id: int
    status: ProcrastinateJobStatus
    error: Optional[str] = None
    events: List[JobEvent] = Field(default_factory=list)


################################################################################################################
# 服务自描述（根路由）


################################################################################################################
@final
class ApiRouteInfo(BaseModel):
    """已注册路由的摘要信息（根路由自描述用）。"""

    path: str
    name: str
    methods: List[str]
    tags: List[str]


################################################################################################################
@final
class ServerInfoResponse(BaseModel):
    """根路由响应：服务自描述信息

    有了这个 response_model，OpenAPI 才能生成具体字段，前端无需再手写收窄层。
    """

    service: str
    base_url: str
    assets_url_prefix: str
    description: str
    status: str
    timestamp: datetime
    version: str
    routes: List[ApiRouteInfo]
