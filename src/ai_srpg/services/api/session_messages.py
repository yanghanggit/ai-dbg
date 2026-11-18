"""玩家会话消息增量查询接口。

会话历史是用户级、append-only 的，不要求当前存在游戏；当前实现只要求房间与
会话仍在内存中（持久化待接入数据库）。
"""

from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger

from ...session.errors import RoomNotFoundError
from ..dependencies import CurrentGameServer
from .schemas import SessionMessageResponse

################################################################################################################
session_messages_api_router = APIRouter(tags=["session-messages"])


################################################################################################################
@session_messages_api_router.get(
    "/api/session_messages/v1/{user_name}/since",
    response_model=SessionMessageResponse,
)
async def get_session_messages(
    game_server: CurrentGameServer,
    user_name: str,
    last_sequence_id: int = Query(..., alias="last_sequence_id"),
) -> SessionMessageResponse:
    """增量查询玩家会话消息接口。

    会话是用户级历史，不要求当前存在游戏；只要房间/会话还在即可读。
    """

    logger.info(
        f"get_session_messages: user_name={user_name}, last_sequence_id={last_sequence_id}"
    )

    # 读路径不取房间锁：单事件循环下 has_room + get_room 之间没有 await
    current_room = game_server.get_room(user_name)
    if current_room is None:
        raise RoomNotFoundError(user_name)

    player_session = current_room.player_session
    if player_session is None:
        logger.error(f"get_session_messages: {user_name} has no session")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有会话",
        )

    # 会话历史与当前游戏无关，直接按用户级 sequence 增量读取
    messages = player_session.get_messages_since(last_sequence_id)
    return SessionMessageResponse(session_messages=messages)
