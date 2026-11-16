"""玩家会话消息服务模块"""

from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger

from ..models import (
    SessionMessageResponse,
)
from .game_server_dependencies import CurrentGameServer

###################################################################################################################################################################
player_session_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
# API增加增量查询端点（唯一读取入口：显式一次性拉取；实时性由客户端定时轮询 + 任务终态即时拉取保证）
@player_session_api_router.get(
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

    # 检查房间是否存在
    if not game_server.has_room(user_name):
        # logger.error(f"get_session_messages: {user_name} has no room")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有房间",
        )

    # 获取房间实例并检查用户会话是否存在
    current_room = game_server.get_room(user_name)
    assert current_room is not None, "get_session_messages: room instance is None"
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
