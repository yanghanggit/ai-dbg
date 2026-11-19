"""玩家房间（会话容器）的生命周期接口。

无鉴权阶段：路径里的 ``user_name`` 就是身份。进入房间等价于登录——没有则创建，
已有则复用；用户级会话随之绑定，与是否已开局无关（房间与游戏是两个生命周期）。
"""

from fastapi import APIRouter, Response, status

from ...gameplay.session_history import open_session
from ...session.access import require_room
from ...session.errors import RoomNotFoundError
from ...session.room import Room
from ..dependencies import CurrentRoomRegistry
from .schemas import RoomStateResponse

################################################################################################################
rooms_api_router = APIRouter(prefix="/api/rooms/v1", tags=["rooms"])


################################################################################################################
def room_state(room: Room) -> RoomStateResponse:
    """把房间内存态映射成传输契约。"""
    session = room.session
    return RoomStateResponse(
        user_name=room.user_name,
        game=room.game.name if room.game is not None else None,
        session_event_sequence=session.event_sequence if session is not None else 0,
    )


################################################################################################################
@rooms_api_router.post(
    "/{user_name}",
    response_model=RoomStateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="进入房间（不存在则创建）",
)
async def enter_room(
    room_registry: CurrentRoomRegistry, user_name: str, response: Response
) -> RoomStateResponse:
    """进入房间，幂等；新建返回 201，复用已有房间返回 200。"""

    room = room_registry.get_room(user_name)
    if room is not None:
        response.status_code = status.HTTP_200_OK
    else:
        room = await room_registry.create_room(user_name)

    # 会话与游戏互不依赖：先进入房间，之后再开局
    async with room.transaction():
        if room.session is None:
            room.set_session(open_session(user_name))

    return room_state(room)


################################################################################################################
@rooms_api_router.get(
    "/{user_name}",
    response_model=RoomStateResponse,
    summary="查询房间状态",
)
async def get_room(
    room_registry: CurrentRoomRegistry, user_name: str
) -> RoomStateResponse:
    """查询房间当前状态；房间不存在时抛 ``RoomNotFoundError``（404）。"""

    return room_state(require_room(room_registry, user_name))


################################################################################################################
@rooms_api_router.delete(
    "/{user_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="离开房间（等待进行中的事务结束）",
)
async def leave_room(room_registry: CurrentRoomRegistry, user_name: str) -> Response:
    """移除并关闭房间；房间不存在时抛 ``RoomNotFoundError``（404）。"""

    if await room_registry.remove_room(user_name) is None:
        raise RoomNotFoundError(user_name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
