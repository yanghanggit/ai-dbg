"""房间接口：以用户身份进入 / 查询 / 离开自己的房间。

无鉴权阶段路径里的 ``user_name`` 就是身份；``room_id`` 是内部分局键。
"""

from fastapi import APIRouter, Response, status

from ...gameplay.session_history import open_session
from ...session.access import require_room_of_user
from ...session.errors import RoomNotFoundError
from ...session.room import Room
from ..dependencies import CurrentRoomRegistry
from .schemas import RoomStateResponse, SeatResponse

################################################################################################################
rooms_api_router = APIRouter(prefix="/api/rooms/v1", tags=["rooms"])


################################################################################################################
def room_state(room: Room, user_name: str) -> RoomStateResponse:
    """把房间内存态映射成传输契约（``user_name`` 是发起请求的身份）。"""
    session = room.session_of(user_name)
    return RoomStateResponse(
        room_id=room.room_id,
        owner=room.owner,
        user_name=user_name,
        game=room.game.name if room.game is not None else None,
        session_event_sequence=session.event_sequence if session is not None else 0,
        seats=[SeatResponse(user_name=s.user_name, actor=s.actor) for s in room.seats],
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

    room = room_registry.get_room_of_user(user_name)
    if room is not None:
        response.status_code = status.HTTP_200_OK
    else:
        room = await room_registry.create_room(user_name)

    # 会话与游戏互不依赖：先进入房间，之后再开局
    async with room.transaction():
        if room.session_of(user_name) is None:
            room.attach_session(open_session(room.room_id, user_name))

    return room_state(room, user_name)


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

    return room_state(require_room_of_user(room_registry, user_name), user_name)


################################################################################################################
@rooms_api_router.delete(
    "/{user_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="离开房间（等待进行中的事务结束）",
)
async def leave_room(room_registry: CurrentRoomRegistry, user_name: str) -> Response:
    """离开房间：移除自己的席位；房间空了就关闭。房间不存在时抛 404。"""

    if await room_registry.leave_room(user_name) is None:
        raise RoomNotFoundError(user_name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
