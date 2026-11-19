import asyncio
import contextlib
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Optional

import click
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from starlette.types import Scope

from ai_srpg import __version__
from ai_srpg.gameplay.jobs import (
    advance_game_job,  # noqa: F401  # 注册 Procrastinate task
)
from ai_srpg.gameplay.scheduler import run_gameplay_scheduler
from ai_srpg.models import ASSETS_URL_PREFIX
from ai_srpg.paths import ASSETS_DIR, LOGS_DIR
from ai_srpg.pgsql import procrastinate_app
from ai_srpg.services.api.routes import API_ROUTERS
from ai_srpg.services.api.schemas import ApiRouteInfo, ServerInfoResponse
from ai_srpg.services.http_errors import register_room_error_handlers
from ai_srpg.session.registry import RoomRegistry
from ai_srpg.session.runtime import bind_runtime_room_registry

load_dotenv()


async def _room_reaper(
    room_registry: RoomRegistry, ttl: float, interval: float
) -> None:
    """周期性回收空闲超时且不在忙的房间。"""
    while True:
        await asyncio.sleep(interval)
        try:
            reaped = await room_registry.reap_expired(ttl)
        except Exception as e:
            logger.error(f"room reaper error: {e}")
            continue
        if reaped:
            logger.info(f"🧹 回收空闲房间: {reaped}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """在 FastAPI 生命周期内打开 Procrastinate 并嵌入运行 worker（与 RoomRegistry 单例同进程/同事件循环）"""
    async with procrastinate_app.open_async():
        room_registry = RoomRegistry()
        app.state.room_registry = room_registry
        bind_runtime_room_registry(room_registry)
        worker_task = asyncio.create_task(
            procrastinate_app.run_worker_async(install_signal_handlers=False)
        )
        room_ttl = float(os.environ.get("GAME_ROOM_TTL_SECONDS", "1800"))
        reaper_interval = float(os.environ.get("GAME_ROOM_REAP_INTERVAL_SECONDS", "60"))
        reaper_task: Optional[asyncio.Task[None]] = None
        if room_ttl > 0:
            reaper_task = asyncio.create_task(
                _room_reaper(room_registry, room_ttl, reaper_interval)
            )
        tick_interval = float(os.environ.get("GAME_TICK_INTERVAL_SECONDS", "60"))
        scheduler_task: Optional[asyncio.Task[None]] = None
        if tick_interval > 0:
            scheduler_task = asyncio.create_task(
                run_gameplay_scheduler(room_registry, tick_interval)
            )
        try:
            yield
        finally:
            if reaper_task is not None:
                reaper_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await asyncio.wait_for(reaper_task, timeout=10)
            if scheduler_task is not None:
                scheduler_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await asyncio.wait_for(scheduler_task, timeout=10)
            worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.wait_for(worker_task, timeout=10)


#: OpenAPI 的标签分组：顺序决定 /docs 里分组的呈现顺序
OPENAPI_TAGS = [
    {"name": "meta", "description": "服务自描述与路由清单"},
    {"name": "rooms", "description": "玩家房间（会话容器）的生命周期；进入房间即登录"},
    {"name": "games", "description": "房间内的游戏局：开局、推进、快照"},
    {"name": "session-messages", "description": "用户级会话历史的增量读取"},
    {"name": "components", "description": "ECS 组件类名清单"},
    {"name": "entities", "description": "实体状态的只读查询"},
    {"name": "jobs", "description": "后台 job 的队列状态、执行事件与 SSE 监听"},
]

app = FastAPI(
    title="AI SRPG 游戏服务器",
    version=__version__,
    description="ECS 世界状态 + 后台 job 的常驻服务端；无鉴权阶段：路径中的 user_name 即身份。",
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)
register_room_error_handlers(app)


@app.get(
    path="/", response_model=ServerInfoResponse, tags=["meta"], summary="服务自描述"
)
async def get_api_info(request: Request) -> ServerInfoResponse:
    """根路由：返回服务信息与已注册路由清单（供客户端自发现）。"""
    from fastapi.routing import APIRoute

    base_url = str(request.base_url)
    logger.info(f"获取API路由信息: {base_url}")

    # 收集所有已注册的路由信息
    # FastAPI 把 APIRoute.tags 标注为 list[str | Enum]；本项目只用字符串标签，
    # 这里统一成 str 以匹配 ServerInfoResponse 的字段类型。
    routes_info: list[ApiRouteInfo] = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            routes_info.append(
                ApiRouteInfo(
                    path=route.path,
                    name=route.name,
                    methods=list(route.methods),
                    tags=[str(tag) for tag in route.tags] if route.tags else [],
                )
            )

    return ServerInfoResponse(
        service="AI SRPG Game Server",
        base_url=base_url,
        assets_url_prefix=ASSETS_URL_PREFIX,
        description="AI SRPG Game Server API Root Endpoint",
        status="healthy",
        timestamp=datetime.now(),
        version=__version__,
        routes=routes_info,
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


############################################################################################################
# 挂载静态文件服务
class AssetStaticFiles(StaticFiles):
    """资源静态服务。

    资源文件名内容寻址（``<UTC时间戳>_<uuid>``，生成后永不改写），因此可安全地
    声明为不可变资源，让浏览器/CDN 长期缓存、连条件请求（304）都不再发起。
    """

    _CACHE_CONTROL = "public, max-age=31536000, immutable"

    def file_response(
        self,
        full_path: str | os.PathLike[str],
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = 200,
    ) -> Response:
        response = super().file_response(full_path, stat_result, scope, status_code)
        response.headers["cache-control"] = self._CACHE_CONTROL
        return response


app.mount(
    ASSETS_URL_PREFIX,
    AssetStaticFiles(directory=str(ASSETS_DIR)),
    name=ASSETS_URL_PREFIX.lstrip("/"),
)

# 注册各个 API 路由
for _router in API_ROUTERS:
    app.include_router(router=_router)


@click.command()
@click.option(
    "--host",
    default="0.0.0.0",
    show_default=True,
    help="监听地址",
)
@click.option(
    "--port",
    type=int,
    envvar="GAME_SERVER_PORT",
    required=True,
    show_envvar=True,
    help="监听端口（未传入时回退读取 .env 的 GAME_SERVER_PORT）",
)
def main(host: str, port: int) -> None:
    """启动 AI SRPG 游戏服务器（uvicorn）。

    port 可通过 --port 传入；未传入时回退读取 .env 中的 GAME_SERVER_PORT。
    """

    import datetime

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_game_server_{_timestamp}.log"
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )
    logger.add(_log_file, level="DEBUG")
    logger.info(f"日志配置: 级别=DEBUG, 文件路径={_log_file}")

    logger.info(f"启动游戏服务器，地址: {host}, 端口: {port}")

    import uvicorn

    uvicorn.run(
        app,
        host=host,
        port=port,
    )


if __name__ == "__main__":
    main()
