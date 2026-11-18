"""HTTP 路由聚合：进程入口只依赖 ``API_ROUTERS`` 完成挂载。"""

from fastapi import APIRouter

from .components import components_api_router
from .entities import entities_api_router
from .jobs import jobs_api_router
from .session_messages import session_messages_api_router

API_ROUTERS: tuple[APIRouter, ...] = (
    session_messages_api_router,
    components_api_router,
    entities_api_router,
    jobs_api_router,
)

__all__ = ["API_ROUTERS"]
