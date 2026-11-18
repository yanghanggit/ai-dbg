"""实体索引与基本查询。

只负责「按名称/组件定位实体」，不包含场景分组、序列化和蓝图构建。
"""

from typing import Optional

from ...entitas import Entity, Matcher
from ...models import (
    ActorComponent,
    PlayerComponent,
    StageComponent,
    WorldComponent,
)
from ..context import SRPGGame


def get_world_entity(srpg_game: SRPGGame, world_name: str) -> Optional[Entity]:
    """通过世界名称获取世界实体。"""
    entity = srpg_game.get_entity_by_name(world_name)
    if entity is not None and entity.has(WorldComponent):
        return entity
    return None


def get_stage_entity(srpg_game: SRPGGame, stage_name: str) -> Optional[Entity]:
    """通过场景名称获取场景实体。"""
    entity = srpg_game.get_entity_by_name(stage_name)
    if entity is not None and entity.has(StageComponent):
        return entity
    return None


def get_actor_entity(srpg_game: SRPGGame, actor_name: str) -> Optional[Entity]:
    """通过角色名称获取角色实体。"""
    entity = srpg_game.get_entity_by_name(actor_name)
    if entity is not None and entity.has(ActorComponent):
        return entity
    return None


def resolve_stage_entity(srpg_game: SRPGGame, entity: Entity) -> Optional[Entity]:
    """解析并返回 Stage 实体。"""
    if entity.has(StageComponent):
        return entity
    elif entity.has(ActorComponent):
        actor_comp = entity.get(ActorComponent)
        return get_stage_entity(srpg_game, actor_comp.current_stage)

    assert False, f"无法解析 Stage 实体，传入的实体既不是 Stage 也不是 Actor: {entity}"
    return None


def get_player_entity(srpg_game: SRPGGame) -> Optional[Entity]:
    """获取玩家实体。"""
    player_entities = srpg_game.get_group(Matcher(all_of=[PlayerComponent])).entities
    assert len(player_entities) == 1, "There should be exactly one player entity."
    return next(iter(player_entities), None)
