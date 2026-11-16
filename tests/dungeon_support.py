"""测试辅助：直接在 ECS 中构造副本/房间/战斗状态。"""

from datetime import datetime, timezone
from typing import Any

from ai_dbg.entitas import Entity
from ai_dbg.game.entities import create_entity
from ai_dbg.models import (
    CombatComponent,
    CurrentDungeonRoomComponent,
    DungeonComponent,
    DungeonRoomComponent,
    DungeonRoomType,
    DungeonRunComponent,
    StageComponent,
)


def make_dungeon_entity(
    game: Any,
    *,
    name: str = "副本.测试",
    profile: str = "profile",
) -> Entity:
    """创建只带 DungeonRunComponent 的副本实体。"""
    entity = create_entity(game, name)
    entity.add(
        DungeonRunComponent,
        name,
        profile,
        datetime.now(timezone.utc),
        {},
    )
    return entity


def make_room_entity(
    game: Any,
    *,
    name: str,
    index: int,
    room_type: DungeonRoomType = DungeonRoomType.COMBAT,
    dungeon_name: str = "副本.测试",
) -> Entity:
    """创建房间实体（当前实现中房间实体就是对应 Stage 实体）。"""
    existing = game.entity_index.get(name)
    entity = existing if existing is not None else create_entity(game, name)
    entity.replace(StageComponent, name)
    entity.replace(DungeonComponent, name)
    entity.replace(
        DungeonRoomComponent,
        name,
        dungeon_name,
        index,
        room_type,
    )
    return entity


def set_current_room(game: Any, room: Entity) -> None:
    """把 room 标记为当前房间。"""
    room.replace(CurrentDungeonRoomComponent, room.name)


def install_combat(
    game: Any,
    combat: Any,
    *,
    room_name: str = "场景.测试",
    index: int = 0,
    dungeon_name: str = "副本.测试",
) -> Any:
    """把任意 combat 对象挂到当前战斗房间上，返回该对象。"""
    room = make_room_entity(
        game,
        name=room_name,
        index=index,
        room_type=DungeonRoomType.COMBAT,
        dungeon_name=dungeon_name,
    )
    set_current_room(game, room)
    if room.has(CombatComponent):
        room.remove(CombatComponent)
    room.set(
        CombatComponent,
        CombatComponent.model_construct(name=room.name, combat=combat),
    )
    return combat


def install_opening_room(
    game: Any,
    *,
    room_name: str = "场景.开场",
    index: int = 0,
    dungeon_name: str = "副本.测试",
) -> Entity:
    """把 room 设为当前开场房间。"""
    room = make_room_entity(
        game,
        name=room_name,
        index=index,
        room_type=DungeonRoomType.OPENING,
        dungeon_name=dungeon_name,
    )
    set_current_room(game, room)
    return room


def clear_current_room(game: Any) -> None:
    """移除当前房间标记。"""
    for entity in list(game.ecs.entities):
        if entity.has(CurrentDungeonRoomComponent):
            entity.remove(CurrentDungeonRoomComponent)
