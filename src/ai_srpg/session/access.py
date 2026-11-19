"""运行期读取入口：把「谁」解析成房间、席位与游戏。

只做读取与前置校验，不进入房间锁；写状态走 ``RoomRegistry.acquire``。
"""

from ..game.context import SRPGGame
from .errors import GameNameMismatchError, GameNotFoundError, RoomNotFoundError
from .registry import RoomRegistry
from .room import Room, Seat


###############################################################################
def require_room_of_user(room_registry: RoomRegistry, user_name: str) -> Room:
    """取该用户所在的房间；不存在时抛 ``RoomNotFoundError``（同时刷新活跃时间）。"""
    room = room_registry.get_room_of_user(user_name)
    if room is None:
        raise RoomNotFoundError(user_name)
    return room


###############################################################################
def require_seat(room: Room, user_name: str) -> Seat:
    """取房间内的席位；用户不在房里时抛 ``RoomNotFoundError``。"""
    seat = room.seat(user_name)
    if seat is None:
        raise RoomNotFoundError(room.room_id)
    return seat


###############################################################################
def require_room_with_game(
    room_registry: RoomRegistry, user_name: str, game_name: str
) -> Room:
    """取用户所在房间，并校验房内游戏名；无房间 / 无游戏 / 名不符分别抛领域异常。"""
    room = require_room_of_user(room_registry, user_name)

    game = room.game
    if game is None:
        raise GameNotFoundError(room_id=room.room_id)

    if game.name != game_name:
        raise GameNameMismatchError(room_id=room.room_id)

    return room


###############################################################################
def require_game_of_user(
    room_registry: RoomRegistry, user_name: str, game_name: str
) -> SRPGGame:
    """取用户所在房间的当前游戏（名字必须匹配）。"""
    room = require_room_with_game(room_registry, user_name, game_name)
    assert room.game is not None, "校验通过后房间必然有游戏"
    return room.game


###############################################################################
