"""用户级会话历史的增量读取接口。

会话历史是 append-only 的持久化数据，与「当前是否有房间 / 是否有游戏」无关：
只按用户 + 序号游标读取。实时性由客户端轮询 + job 终态即时拉取保证。
"""

from fastapi import APIRouter, Query
from loguru import logger

from ...gameplay.session_history import (
    DatabaseSessionMessageStore,
    SessionMessageStore,
)
from .schemas import SessionMessageResponse

################################################################################################################
session_messages_api_router = APIRouter(tags=["session-messages"])


################################################################################################################
def _session_store() -> SessionMessageStore:
    """存储入口；测试可替换这一层，避免访问数据库。"""
    return DatabaseSessionMessageStore()


################################################################################################################
@session_messages_api_router.get(
    "/api/session_messages/v1/{user_name}/since",
    response_model=SessionMessageResponse,
)
async def get_session_messages(
    user_name: str,
    last_sequence_id: int = Query(..., alias="last_sequence_id"),
    limit: int = Query(default=500, ge=1, le=2000),
) -> SessionMessageResponse:
    """按序号增量读取会话历史（升序返回）。"""

    logger.info(
        f"get_session_messages: user_name={user_name}, last_sequence_id={last_sequence_id}, limit={limit}"
    )

    messages = _session_store().messages_since(user_name, last_sequence_id, limit=limit)
    return SessionMessageResponse(session_messages=messages)
