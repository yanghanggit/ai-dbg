"""副本与场景状态查询。"""

from typing import List, Optional

from ..entitas import Entity, Matcher
from ..models import (
    Combat,
    CombatComponent,
    CurrentDungeonRoomComponent,
    DungeonComponent,
    DungeonRoomComponent,
    DungeonRoomType,
    DungeonRoomView,
    DungeonRunComponent,
    DungeonStateView,
)
from .context import DBGGame
from .entities import (
    get_player_entity,
    is_actor_in_dungeon_stage,
    is_actor_in_lobby_stage,
)


###############################################################################################################################################
def get_dungeon_entity(dbg_game: DBGGame) -> Optional[Entity]:
    """返回当前副本实体；同一世界最多一个。"""
    entities = dbg_game.ecs.get_group(
        Matcher(all_of=[DungeonRunComponent])
    ).entities
    assert len(entities) <= 1, "同一世界最多只能有一个副本实体"
    return next(iter(entities), None)


###############################################################################################################################################
def current_dungeon_name(dbg_game: DBGGame) -> str:
    """返回当前副本名；没有副本时返回空串。"""
    dungeon_entity = get_dungeon_entity(dbg_game)
    return dungeon_entity.name if dungeon_entity is not None else ""


###############################################################################################################################################
def dungeon_rooms(dbg_game: DBGGame) -> List[Entity]:
    """按 room index 返回当前副本的全部房间实体（房间即对应 Stage 实体）。"""
    room_entities = dbg_game.ecs.get_group(
        Matcher(all_of=[DungeonRoomComponent])
    ).entities
    return sorted(
        room_entities,
        key=lambda entity: _require_room_component(entity).index,
    )


###############################################################################################################################################
def get_dungeon_room_by_index(
    dbg_game: DBGGame, index: int
) -> Optional[Entity]:
    """按 room index 获取房间实体。"""
    for room_entity in dungeon_rooms(dbg_game):
        if _require_room_component(room_entity).index == index:
            return room_entity
    return None


###############################################################################################################################################
def current_dungeon_room(dbg_game: DBGGame) -> Optional[Entity]:
    """返回当前所在房间实体；尚未进入副本时返回 None。"""
    room_entities = dbg_game.ecs.get_group(
        Matcher(all_of=[CurrentDungeonRoomComponent])
    ).entities
    assert len(room_entities) <= 1, "同一时刻最多只能有一个当前副本房间"
    return next(iter(room_entities), None)


###############################################################################################################################################
def current_room_index(dbg_game: DBGGame) -> int:
    """返回当前房间索引；尚未进入副本时返回 -1。"""
    room_entity = current_dungeon_room(dbg_game)
    if room_entity is None:
        return -1
    return _require_room_component(room_entity).index


###############################################################################################################################################
def current_dungeon_combat_room(dbg_game: DBGGame) -> Entity:
    """断言当前处于战斗房间中，返回战斗房间实体。"""
    room_entity = current_dungeon_room(dbg_game)
    assert room_entity is not None, "当前副本房间不存在"
    assert (
        _require_room_component(room_entity).room_type == DungeonRoomType.COMBAT
    ), "当前副本房间不是战斗房间"
    assert room_entity.has(CombatComponent), "当前战斗房间缺少 CombatComponent"
    return room_entity


###############################################################################################################################################
def current_dungeon_combat(dbg_game: DBGGame) -> Combat:
    """返回当前战斗实例；调用方应先用 is_current_room_dungeon_combat 守卫。"""
    room_entity = current_dungeon_combat_room(dbg_game)
    combat_component = room_entity.get(CombatComponent)
    assert combat_component is not None, "当前战斗房间缺少 CombatComponent"
    return combat_component.combat


###############################################################################################################################################
def is_dungeon_setup_entities(dbg_game: DBGGame) -> bool:
    """检查当前副本的实体是否已全部创建。"""
    dungeon_entity = get_dungeon_entity(dbg_game)
    if dungeon_entity is None:
        return False
    rooms = dungeon_rooms(dbg_game)
    if not rooms:
        return False
    for room_entity in rooms:
        if not room_entity.has(DungeonComponent):
            return False
        if not room_entity.has(DungeonRoomComponent):
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
def is_current_room_dungeon_combat(dbg_game: DBGGame) -> bool:
    room_entity = current_dungeon_room(dbg_game)
    if room_entity is None:
        return False
    return (
        _require_room_component(room_entity).room_type == DungeonRoomType.COMBAT
    )


###############################################################################################################################################
def is_current_room_dungeon_opening(dbg_game: DBGGame) -> bool:
    room_entity = current_dungeon_room(dbg_game)
    if room_entity is None:
        return False
    return (
        _require_room_component(room_entity).room_type == DungeonRoomType.OPENING
    )


###############################################################################################################################################
def dungeon_room_view(room_entity: Entity) -> DungeonRoomView:
    """把一个房间实体投影成 API 视图。"""
    room_component = _require_room_component(room_entity)
    combat_component = room_entity.get(CombatComponent)
    return DungeonRoomView(
        name=room_entity.name,
        index=room_component.index,
        type=room_component.room_type,
        combat=combat_component.combat if combat_component is not None else None,
    )


###############################################################################################################################################
def dungeon_state_view(dbg_game: DBGGame) -> DungeonStateView:
    """把 ECS 中的副本状态投影成 API 视图。"""
    dungeon_entity = get_dungeon_entity(dbg_game)
    if dungeon_entity is None:
        return DungeonStateView(
            name="",
            profile="",
            created_at=None,
            assets={},
            current_room_index=-1,
            rooms=[],
        )

    dungeon_run = dungeon_entity.get(DungeonRunComponent)
    assert dungeon_run is not None, "副本实体缺少 DungeonRunComponent"
    return DungeonStateView(
        name=dungeon_entity.name,
        profile=dungeon_run.profile,
        created_at=dungeon_run.created_at,
        assets=dungeon_run.assets,
        current_room_index=current_room_index(dbg_game),
        rooms=[dungeon_room_view(room_entity) for room_entity in dungeon_rooms(dbg_game)],
    )


###############################################################################################################################################
def _require_room_component(room_entity: Entity) -> DungeonRoomComponent:
    room_component = room_entity.get(DungeonRoomComponent)
    assert room_component is not None, f"{room_entity.name} 缺少 DungeonRoomComponent"
    return room_component
