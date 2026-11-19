"""房间与游戏状态相关的领域异常；状态码映射见 ``services.http_errors``。"""


###############################################################################
class RoomNotFoundError(Exception):
    """请求的房间不存在。"""

    def __init__(self, room_id: str) -> None:
        super().__init__(f"room not found: {room_id}")
        self.room_id: str = room_id


###############################################################################
class RoomAlreadyExistsError(Exception):
    """创建房间时同号房间已存在。"""

    def __init__(self, room_id: str) -> None:
        super().__init__(f"room already exists: {room_id}")
        self.room_id: str = room_id


###############################################################################
class RoomClosedError(RuntimeError):
    """在已关闭的房间上进入事务或加入席位时抛出。"""

    def __init__(self, room_id: str) -> None:
        super().__init__(f"room closed: {room_id}")
        self.room_id: str = room_id


###############################################################################
class RoomJobBusyError(RuntimeError):
    """该房间已有 job 排队（``room.is_busy`` 表示房间锁被占用，两者不同）。"""

    def __init__(self, room_id: str) -> None:
        super().__init__(f"room job busy: {room_id}")
        self.room_id: str = room_id


###############################################################################
class GameStateError(Exception):
    """游戏状态不满足操作前置条件。"""

    detail: str = "游戏状态非法"

    def __init__(self, *, room_id: str = "") -> None:
        super().__init__(self.detail)
        self.room_id: str = room_id


###############################################################################
class GameNotFoundError(GameStateError):
    """房间内没有游戏实例。"""

    detail = "没有游戏，请先登录"


###############################################################################
class GameNameMismatchError(GameStateError):
    """请求的游戏名与房间内当前游戏不一致。"""

    detail = "游戏名称不匹配"


###############################################################################
