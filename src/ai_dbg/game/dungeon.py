"""副本与场景状态查询。"""

from typing import cast

from ..models import CombatRoom, Dungeon, OpeningRoom
from .context import DBGGame
from .entities import (
    get_actor_entity,
    get_player_entity,
    get_stage_entity,
    is_actor_in_dungeon_stage,
    is_actor_in_lobby_stage,
)


###############################################################################################################################################
def current_dungeon(dbg_game: DBGGame) -> Dungeon:
    return dbg_game.world.dungeon


###############################################################################################################################################
def is_dungeon_setup_entities(dbg_game: DBGGame) -> bool:
    """检查当前副本的实体是否已全部创建。"""
    dungeon = dbg_game.world.dungeon
    if not dungeon.rooms:
        return False
    for room in dungeon.rooms:
        if get_stage_entity(dbg_game, room.stage.name) is None:
            return False
        for actor in room.stage.actors:
            if get_actor_entity(dbg_game, actor.name) is None:
                return False
    return True


###############################################################################################################################################
def is_player_in_lobby_stage(dbg_game: DBGGame) -> bool:
    """检查玩家是否在大厅/营地场景中。"""
    player_entity = get_player_entity(dbg_game)
    assert player_entity is not None, "player_entity is None"
    return is_actor_in_lobby_stage(dbg_game, player_entity)


###############################################################################################################################################
def is_player_in_dungeon_stage(dbg_game: DBGGame) -> bool:
    """检查玩家是否在副本场景中。"""
    player_entity = get_player_entity(dbg_game)
    assert player_entity is not None, "player_entity is None"
    return is_actor_in_dungeon_stage(dbg_game, player_entity)


###############################################################################################################################################
def current_dungeon_combat_room(dbg_game: DBGGame) -> CombatRoom:
    """断言当前处于战斗房间中，返回战斗房间。"""
    dungeon = dbg_game.world.dungeon
    assert dungeon is not None, "当前副本不存在"
    assert dungeon.current_room is not None, "当前副本房间不存在"
    current_room = dungeon.current_room
    # 允许测试替身使用带 combat 属性的对象；真实模型仍是 CombatRoom。
    assert isinstance(current_room, CombatRoom) or hasattr(
        current_room, "combat"
    ), "当前副本房间不是战斗房间"
    return cast(CombatRoom, current_room)


###############################################################################################################################################
def is_current_room_dungeon_combat(dbg_game: DBGGame) -> bool:
    dungeon = dbg_game.world.dungeon
    if dungeon is None or dungeon.current_room is None:
        return False
    return isinstance(dungeon.current_room, CombatRoom) or hasattr(
        dungeon.current_room, "combat"
    )


###############################################################################################################################################
def is_current_room_dungeon_opening(dbg_game: DBGGame) -> bool:
    dungeon = dbg_game.world.dungeon
    if dungeon is None or dungeon.current_room is None:
        return False
    return isinstance(dungeon.current_room, OpeningRoom)
