"""运行期状态的读取入口：把 ``(用户, 游戏名)`` 解析成内存对象。

HTTP 层与定时器共用这一层，避免每个入口各自重复「查房间 → 取游戏 → 校验游戏名」
的样板代码。只做读取与前置校验，不进入房间锁；需要写状态时仍用
``GameServer.acquire``。
"""

from ..game.context import SRPGGame
from .errors import GameNameMismatchError, GameNotFoundError, RoomNotFoundError
from .room import PlayerRoom
from .server import GameServer


###############################################################################
def require_room(game_server: GameServer, user_name: str) -> PlayerRoom:
    """取房间；不存在时抛 ``RoomNotFoundError``（同时刷新房间活跃时间）。"""
    room = game_server.get_room(user_name)
    if room is None:
        raise RoomNotFoundError(user_name)
    return room


###############################################################################
def require_game(game_server: GameServer, user_name: str, game_name: str) -> SRPGGame:
    """取房间内当前游戏；无房间 / 无游戏 / 游戏名不符分别抛领域异常。"""
    room = require_room(game_server, user_name)

    game = room.game
    if game is None:
        raise GameNotFoundError(user_name=user_name)

    if game.name != game_name:
        raise GameNameMismatchError(user_name=user_name)

    return game
