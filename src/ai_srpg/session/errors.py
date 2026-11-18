"""房间与会话相关的领域异常。

这些异常描述「房间/游戏状态不满足前置条件」，不依赖 HTTP 与任务队列；
对外的状态码映射集中在 ``services/http_errors``。
"""


###############################################################################
class RoomNotFoundError(Exception):
    """请求的房间不存在。"""

    def __init__(self, user_name: str) -> None:
        super().__init__(f"room not found: {user_name}")
        self.user_name: str = user_name


###############################################################################
class RoomAlreadyExistsError(Exception):
    """创建房间时同名房间已存在。"""

    def __init__(self, user_name: str) -> None:
        super().__init__(f"room already exists: {user_name}")
        self.user_name: str = user_name


###############################################################################
class RoomClosedError(RuntimeError):
    """在已关闭的房间上进入事务时抛出。"""

    def __init__(self, username: str) -> None:
        super().__init__(f"room closed: {username}")
        self.username: str = username


###############################################################################
class RoomJobBusyError(RuntimeError):
    """该房间已有 job 排队（``room.is_busy`` 表示房间锁被占用，两者不同）。"""

    def __init__(self, user_name: str) -> None:
        super().__init__(f"room job busy: {user_name}")
        self.user_name: str = user_name


###############################################################################
class GameStateError(Exception):
    """游戏状态不满足操作前置条件。"""

    detail: str = "游戏状态非法"

    def __init__(self, *, user_name: str = "") -> None:
        super().__init__(self.detail)
        self.user_name: str = user_name


###############################################################################
class GameNotFoundError(GameStateError):
    """玩家没有游戏实例。"""

    detail = "没有游戏，请先登录"


###############################################################################
