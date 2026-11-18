"""领域异常到 HTTP 状态码的统一映射。

领域异常本身只描述前置条件失败（``session.errors``）；状态码与文案属于本层，
集中在这里，避免领域代码携带 HTTP 语义。
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from ..session.errors import (
    GameNotFoundError,
    GameStateError,
    RoomAlreadyExistsError,
    RoomClosedError,
    RoomJobBusyError,
    RoomNotFoundError,
)


###############################################################################
def register_room_error_handlers(app: FastAPI) -> None:
    """注册房间与游戏状态相关的领域异常处理器。"""

    @app.exception_handler(RoomNotFoundError)
    async def _room_not_found(request: Request, exc: RoomNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "没有房间，请先登录"},
        )

    @app.exception_handler(RoomClosedError)
    async def _room_closed(request: Request, exc: RoomClosedError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "房间已关闭，请重新登录"},
        )

    @app.exception_handler(RoomAlreadyExistsError)
    async def _room_exists(
        request: Request, exc: RoomAlreadyExistsError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "房间已存在"},
        )

    @app.exception_handler(RoomJobBusyError)
    async def _room_job_busy(request: Request, exc: RoomJobBusyError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "该房间已有 job 在进行中，请稍后重试"},
        )

    @app.exception_handler(GameNotFoundError)
    async def _game_not_found(request: Request, exc: GameNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": exc.detail},
        )

    @app.exception_handler(GameStateError)
    async def _game_state_error(request: Request, exc: GameStateError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": exc.detail},
        )


###############################################################################
