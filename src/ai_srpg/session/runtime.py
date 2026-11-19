"""进程级 RoomRegistry 的运行时访问。

HTTP 路径用 ``services.dependencies.CurrentRoomRegistry``（Request 上下文）；
无 Request 的运行时上下文（当前为后台 job）用 ``get_runtime_room_registry``。
实例由应用启动时的 ``lifespan`` 显式绑定。
"""

from typing import Optional

from .registry import RoomRegistry

_runtime_room_registry: Optional[RoomRegistry] = None


###############################################################################
def bind_runtime_room_registry(room_registry: RoomRegistry) -> None:
    """在应用启动时绑定进程级 RoomRegistry（供非请求上下文使用）。"""
    global _runtime_room_registry
    _runtime_room_registry = room_registry


###############################################################################
def get_runtime_room_registry() -> RoomRegistry:
    """获取进程级 RoomRegistry。"""
    if _runtime_room_registry is None:
        raise RuntimeError("RoomRegistry 尚未初始化")
    return _runtime_room_registry
