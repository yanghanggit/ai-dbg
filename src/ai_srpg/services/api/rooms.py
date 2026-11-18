"""玩家房间（会话容器）的生命周期接口。

无鉴权阶段：路径里的 ``user_name`` 就是身份。进入房间等价于登录——没有则创建，
已有则复用；用户级会话随之绑定，与是否已开局无关（房间与游戏是两个生命周期）。
"""

from fastapi import APIRouter, Response, status

from ...session import PlayerSession
from ...session.access import require_room
from ...session.errors import RoomNotFoundError
from ..dependencies import CurrentGameServer
from .schemas import RoomStateResponse

################################################################################################################
rooms_api_router = APIRouter(prefix="/api/rooms/v1", tags=["rooms"])


################################################################################################################
@rooms_api_router.post(
    "/{user_name}",
    response_model=RoomStateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="进入房间（不存在则创建）",
)
async def enter_room(
    game_server: CurrentGameServer, user_name: str, response: Response
) -> RoomStateResponse:
    """进入房间，幂等；新建返回 201，复用已有房间返回 200。"""

    room = game_server.get_room(user_name)
    if room is not None:
        response.status_code = status.HTTP_200_OK
    else:
        room = await game_server.create_room(user_name)

    # 会话与游戏互不依赖：先进入房间，之后再开局
    async with room.transaction():
        if room.player_session is None:
            room.attach_session(PlayerSession(name=user_name))

    return RoomStateResponse.from_room(room)


################################################################################################################
@rooms_api_router.get(
    "/{user_name}",
    response_model=RoomStateResponse,
    summary="查询房间状态",
)
async def get_room(game_server: CurrentGameServer, user_name: str) -> RoomStateResponse:
    """查询房间当前状态；房间不存在时抛 ``RoomNotFoundError``（404）。"""

    return RoomStateResponse.from_room(require_room(game_server, user_name))


################################################################################################################
@rooms_api_router.delete(
    "/{user_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="离开房间（等待进行中的事务结束）",
)
async def leave_room(game_server: CurrentGameServer, user_name: str) -> Response:
    """移除并关闭房间；房间不存在时抛 ``RoomNotFoundError``（404）。"""

    if await game_server.remove_room(user_name) is None:
        raise RoomNotFoundError(user_name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
