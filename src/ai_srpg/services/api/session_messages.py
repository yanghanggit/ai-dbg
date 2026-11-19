"""会话历史接口：按用户身份读他所在那一局的流，并按其可见性过滤。"""

from fastapi import APIRouter, Query
from loguru import logger

from ...gameplay import session_history
from ...session.registry import RoomRegistry
from ..dependencies import CurrentRoomRegistry
from .schemas import SessionMessageResponse

################################################################################################################
session_messages_api_router = APIRouter(tags=["session-messages"])


################################################################################################################
def _room_id_for(room_registry: RoomRegistry, user_name: str) -> str:
    """用户身份 → 局号；进程内已无房间时回退到用户名（单人阶段两者相同）。"""
    room = room_registry.get_room_of_user(user_name)
    return room.room_id if room is not None else user_name


################################################################################################################
@session_messages_api_router.get(
    "/api/session_messages/v1/{user_name}/since",
    response_model=SessionMessageResponse,
)
async def get_session_messages(
    room_registry: CurrentRoomRegistry,
    user_name: str,
    last_sequence_id: int = Query(..., alias="last_sequence_id"),
    limit: int = Query(default=500, ge=1, le=2000),
) -> SessionMessageResponse:
    """按序号增量读取会话历史（升序返回）。"""

    logger.info(
        f"get_session_messages: user_name={user_name}, last_sequence_id={last_sequence_id}, limit={limit}"
    )

    room_id = _room_id_for(room_registry, user_name)
    messages = session_history.session_store().messages_since(
        room_id, last_sequence_id, viewer=user_name, limit=limit
    )
    return SessionMessageResponse(session_messages=messages)
