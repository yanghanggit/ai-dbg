"""场景内角色查询与归属判定。"""

from typing import Dict, List, Optional, Set

from ...entitas import Entity, Matcher
from ...models import (
    ActorComponent,
    StageComponent,
)
from ..context import SRPGGame
from .repository import resolve_stage_entity


def get_actors_in_stage(
    srpg_game: SRPGGame, entity: Entity, matcher: Optional[Matcher] = None
) -> Set[Entity]:
    """获取指定场景上匹配 matcher 的 Actor 实体。"""
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
    candidate_entities = srpg_game.ecs.get_group(actor_matcher).entities
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
    """获取所有场景到 Actor 的分组映射。"""
    ret: Dict[Entity, List[Entity]] = {}
    actor_entities = srpg_game.ecs.get_group(Matcher(all_of=[ActorComponent])).entities
    for actor_entity in actor_entities:
        stage_entity = resolve_stage_entity(srpg_game, actor_entity)
        assert stage_entity is not None, f"actor_entity = {actor_entity}"
        ret.setdefault(stage_entity, []).append(actor_entity)

    stage_entities = srpg_game.ecs.get_group(Matcher(all_of=[StageComponent])).entities
    for stage_entity in stage_entities:
        if stage_entity not in ret:
            ret.setdefault(stage_entity, [])
    return ret


def get_actors_by_stage_as_names(srpg_game: SRPGGame) -> Dict[str, List[str]]:
    """获取所有场景到 Actor 的分组映射（名称版本）。"""
    ret: Dict[str, List[str]] = {}
    for stage_entity, actor_entities in get_actors_by_stage(srpg_game).items():
        ret[stage_entity.name] = [actor_entity.name for actor_entity in actor_entities]
    return ret
