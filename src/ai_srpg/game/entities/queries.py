"""实体查询：按名称/组件定位实体、舞台分组与归属判定。"""

from typing import Dict, List, Optional, Set

from ...entitas import Entity, Matcher
from ...models import (
    ActorComponent,
    ActorSummary,
    AppearanceComponent,
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
    """所有舞台到其上角色的映射，只含直接归属（不含子舞台里的人）。

    组查询走的是 ``set``（按对象哈希迭代），顺序不可预期；这里统一按实体创建顺序
    排序。舞台是父先子后建的，所以结果恰好是舞台树的先序，同一蓝图每次构建都一样。
    """
    ret: Dict[Entity, List[Entity]] = {}
    actor_entities = srpg_game.get_group(Matcher(all_of=[ActorComponent])).entities
    for actor_entity in sorted(actor_entities, key=lambda entity: entity.index):
        stage_entity = resolve_stage_entity(srpg_game, actor_entity)
        assert stage_entity is not None, f"actor_entity = {actor_entity}"
        ret.setdefault(stage_entity, []).append(actor_entity)

    stage_entities = srpg_game.get_group(Matcher(all_of=[StageComponent])).entities
    for stage_entity in stage_entities:
        ret.setdefault(stage_entity, [])

    return {stage: ret[stage] for stage in sorted(ret, key=lambda entity: entity.index)}


def get_actors_by_stage_as_names(srpg_game: SRPGGame) -> Dict[str, List[str]]:
    """获取所有舞台到 Actor 的分组映射（名称版本）。"""
    ret: Dict[str, List[str]] = {}
    for stage_entity, actor_entities in get_actors_by_stage(srpg_game).items():
        ret[stage_entity.name] = [actor_entity.name for actor_entity in actor_entities]
    return ret


def list_actor_summaries(srpg_game: SRPGGame) -> List[ActorSummary]:
    """所有角色的当前状态，按创建顺序（与快照重放一致）。"""
    actors = srpg_game.get_group(Matcher(all_of=[ActorComponent])).entities
    summaries: List[ActorSummary] = []
    for actor in sorted(actors, key=lambda entity: entity.index):
        summaries.append(
            ActorSummary(
                name=actor.name,
                stage=actor.get(ActorComponent).current_stage,
                player=(
                    actor.get(PlayerComponent).user_name
                    if actor.has(PlayerComponent)
                    else None
                ),
                appearance=(
                    actor.get(AppearanceComponent).appearance
                    if actor.has(AppearanceComponent)
                    else ""
                ),
            )
        )
    return summaries


def get_child_stages(srpg_game: SRPGGame, stage_name: str) -> List[Entity]:
    """某舞台的直接子舞台，按创建顺序（即蓝图里声明的先后）返回。"""
    children = [
        entity
        for entity in srpg_game.get_group(Matcher(all_of=[StageComponent])).entities
        if entity.get(StageComponent).parent_stage == stage_name
    ]
    return sorted(children, key=lambda entity: entity.index)


def get_ancestor_stages(srpg_game: SRPGGame, stage_name: str) -> List[Entity]:
    """某舞台的祖先链，由近到远（父、祖父……），根舞台返回空列表。"""
    ancestors: List[Entity] = []
    entity = get_stage_entity(srpg_game, stage_name)
    assert entity is not None, f"找不到舞台实体: {stage_name}"
    parent_name = entity.get(StageComponent).parent_stage
    while parent_name is not None:
        parent = get_stage_entity(srpg_game, parent_name)
        assert parent is not None, f"舞台 {stage_name} 的父舞台不存在: {parent_name}"
        ancestors.append(parent)
        parent_name = parent.get(StageComponent).parent_stage
    return ancestors


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
