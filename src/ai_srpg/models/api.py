from datetime import datetime
from typing import List, final

from pydantic import BaseModel

from ..entitas import ContextData
from .job import JobEvent, JobSnapshot
from .session_message import SessionMessage


@final
class EntitiesDetailsResponse(BaseModel):
    entities: ContextData


@final
class SessionMessageResponse(BaseModel):
    session_messages: List[SessionMessage]


@final
class JobStatusListResponse(BaseModel):
    jobs: List[JobSnapshot]


@final
class JobEventsResponse(BaseModel):
    job_id: int
    events: List[JobEvent]


@final
class ApiRouteInfo(BaseModel):
    """已注册路由的摘要信息（根路由自描述用）"""

    path: str
    name: str
    methods: List[str]
    tags: List[str]


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
