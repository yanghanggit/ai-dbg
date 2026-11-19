"""实体查询：按名称/组件定位实体、舞台分组与归属判定。"""

from typing import Dict, List, Optional, Set

from ...entitas import Entity, Matcher
from ...models import (
    ActorComponent,
    PlayerComponent,
    StageComponent,
    WorldComponent,
)
from ..context import SRPGGame


def get_actors_in_stage(
    srpg_game: SRPGGame, entity: Entity, matcher: Optional[Matcher] = None
) -> Set[Entity]:
    """获取指定舞台上匹配 matcher 的 Actor 实体。"""
    stage_entity = resolve_stage_entity(srpg_game, entity)
    assert stage_entity is not None, f"entity = {entity}"

    all_of = list(matcher.all_of) if matcher is not None and matcher.all_of else []
    if ActorComponent not in all_of:
        all_of.append(ActorComponent)

    actor_matcher = Matcher(
        all_of=all_of,
        any_of=matcher.any_of if matcher is not None else None,
        none_of=matcher.none_of if matcher is not None else None,
    )

    ret: Set[Entity] = set()
    candidate_entities = srpg_game.get_group(actor_matcher).entities
    for candidate_entity in candidate_entities:
        candidate_stage_entity = resolve_stage_entity(srpg_game, candidate_entity)
        assert (
            candidate_stage_entity is not None
        ), f"candidate_entity = {candidate_entity}"
        if candidate_stage_entity != stage_entity:
            continue
        ret.add(candidate_entity)

    return ret


def get_actors_by_stage(srpg_game: SRPGGame) -> Dict[Entity, List[Entity]]:
    """获取所有舞台到 Actor 的分组映射。"""
    ret: Dict[Entity, List[Entity]] = {}
    actor_entities = srpg_game.get_group(Matcher(all_of=[ActorComponent])).entities
    for actor_entity in actor_entities:
        stage_entity = resolve_stage_entity(srpg_game, actor_entity)
        assert stage_entity is not None, f"actor_entity = {actor_entity}"
        ret.setdefault(stage_entity, []).append(actor_entity)

    stage_entities = srpg_game.get_group(Matcher(all_of=[StageComponent])).entities
    for stage_entity in stage_entities:
        if stage_entity not in ret:
            ret.setdefault(stage_entity, [])
    return ret


def get_actors_by_stage_as_names(srpg_game: SRPGGame) -> Dict[str, List[str]]:
    """获取所有舞台到 Actor 的分组映射（名称版本）。"""
    ret: Dict[str, List[str]] = {}
    for stage_entity, actor_entities in get_actors_by_stage(srpg_game).items():
        ret[stage_entity.name] = [actor_entity.name for actor_entity in actor_entities]
    return ret


def get_world_entity(srpg_game: SRPGGame, world_name: str) -> Optional[Entity]:
    """通过世界名称获取世界实体。"""
    entity = srpg_game.get_entity_by_name(world_name)
    if entity is not None and entity.has(WorldComponent):
        return entity
    return None


def get_stage_entity(srpg_game: SRPGGame, stage_name: str) -> Optional[Entity]:
    """通过舞台名称获取舞台实体。"""
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


def get_player_actor_name(srpg_game: SRPGGame, user_name: str) -> Optional[str]:
    """某玩家控制的角色名；该玩家尚未分到角色时返回 None。"""
    entity = get_player_entity(srpg_game, user_name)
    return entity.name if entity is not None else None


def get_player_entity(srpg_game: SRPGGame, user_name: str) -> Optional[Entity]:
    """某玩家控制的角色实体；该玩家尚未分到角色时返回 None。

    一局里可以有多个 ``PlayerComponent``（一人一个角色），因此必须按身份查，
    不能取「第一个玩家」。同一玩家绑定多个角色是状态损坏，直接报错。
    """
    players = srpg_game.get_group(Matcher(all_of=[PlayerComponent])).entities
    found = [
        entity
        for entity in players
        if entity.get(PlayerComponent).user_name == user_name
    ]
    if len(found) > 1:
        names = [entity.name for entity in found]
        raise ValueError(f"玩家 {user_name} 绑定了多个角色: {names}")
    return found[0] if found else None
