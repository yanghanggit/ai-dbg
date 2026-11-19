"""HTTP 依赖注入：当前用户与进程级 RoomRegistry。

RoomRegistry 单例来自 ``app.state``（由 ``lifespan`` 绑定）；无 Request 的运行时
访问见 ``session.runtime``。
"""

from typing import Annotated, Final, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from ..auth.jwt import decode_jwt_token
from ..pgsql.user_operations import get_user, has_user
from ..session.registry import RoomRegistry

# OAuth2 密码流程的令牌获取端点
oauth2_scheme: Final[OAuth2PasswordBearer] = OAuth2PasswordBearer(tokenUrl="token")


###############################################################################################################################################
async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """获取当前认证用户（FastAPI 依赖注入函数）。"""

    # 解码并验证 JWT 令牌
    try:
        payload = decode_jwt_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 提取用户名
    user_name: Optional[str] = payload.get("sub")
    if user_name is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 验证用户是否存在
    if not has_user(user_name):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    # 获取并返回用户信息
    user_db = get_user(user_name)
    return user_db.user_name


###############################################################################################################################################
def get_room_registry(request: Request) -> RoomRegistry:
    """FastAPI 依赖：从 ``app.state`` 获取进程级 RoomRegistry。"""
    room_registry: RoomRegistry = request.app.state.room_registry
    return room_registry


###############################################################################################################################################
# 类型注解别名，用于 FastAPI 依赖注入
CurrentUser = Annotated[str, Depends(get_current_user)]
CurrentRoomRegistry = Annotated[RoomRegistry, Depends(get_room_registry)]


###############################################################################################################################################
