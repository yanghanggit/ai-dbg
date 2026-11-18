"""路由聚合：进程入口只依赖 ``API_ROUTERS`` 完成挂载。

``services.api`` 包本身保持空 ``__init__``，让客户端可以只 import
``services.api.schemas`` 这个传输契约，而不牵连 FastAPI 路由与数据库。
"""

from fastapi import APIRouter

from .components import components_api_router
from .entities import entities_api_router
from .games import games_api_router
from .jobs import jobs_api_router
from .rooms import rooms_api_router
from .session_messages import session_messages_api_router

API_ROUTERS: tuple[APIRouter, ...] = (
    rooms_api_router,
    games_api_router,
    session_messages_api_router,
    components_api_router,
    entities_api_router,
    jobs_api_router,
)

__all__ = ["API_ROUTERS"]
