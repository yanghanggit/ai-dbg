"""存活角色查询与目标解析。"""

import random
from typing import List, Sequence, Set, Tuple

from ...entitas import Entity, Matcher
from ...models import (
    DeathComponent,
    MonsterComponent,
    PartyMemberComponent,
    TargetType,
)
from ..context import DBGGame
from ..entities import get_actors_in_stage


def get_alive_actors_in_stage(game: DBGGame, entity: Entity) -> Set[Entity]:
    """获取指定场景上存活的 Actor 实体。"""
    return get_actors_in_stage(game, entity, Matcher(none_of=[DeathComponent]))


def get_alive_party_members_in_stage(
    anchor_entity: Entity, dbg_game: DBGGame
) -> List[Entity]:
    """获取锚点实体所在场景中所有存活的队伍成员。"""
    return list(
        get_actors_in_stage(
            dbg_game,
            anchor_entity,
            Matcher(all_of=[PartyMemberComponent], none_of=[DeathComponent]),
        )
    )


def get_alive_monsters_in_stage(
    anchor_entity: Entity, dbg_game: DBGGame
) -> List[Entity]:
    """获取锚点实体所在场景中所有存活的怪物。"""
    return list(
        get_actors_in_stage(
            dbg_game,
            anchor_entity,
            Matcher(all_of=[MonsterComponent], none_of=[DeathComponent]),
        )
    )


def _expand_camp_members(
    anchor_target_name: str,
    actor_entity: Entity,
    dbg_game: DBGGame,
) -> Tuple[List[Entity], str]:
    """将单个阵营锚点目标名展开为该锚点所在阵营的全体存活角色。"""
    # 构建当前场景中所有存活角色的映射，便于根据锚点名称快速查找对应实体。
    alive_map = {e.name: e for e in get_alive_actors_in_stage(dbg_game, actor_entity)}
    anchor_entity = alive_map.get(anchor_target_name)
    if anchor_entity is None:
        return (
            [],
            f"目标 '{anchor_target_name}' 不在当前场景存活角色列表中: {sorted(alive_map)}",
        )

    # 根据锚点实体的阵营类型，返回该阵营的全体存活角色。
    if anchor_entity.has(PartyMemberComponent):
        return get_alive_party_members_in_stage(anchor_entity, dbg_game), ""
    if anchor_entity.has(MonsterComponent):
        return get_alive_monsters_in_stage(anchor_entity, dbg_game), ""

    # 如果锚点实体既不属于队伍也不属于怪物阵营，则返回错误。
    return [], f"目标 '{anchor_target_name}' 不属于任何可识别阵营"


def resolve_targets(
    target_type: TargetType,
    hit_count: int,
    actor_entity: Entity,
    passed_targets: Sequence[str],
    dbg_game: DBGGame,
) -> Tuple[List[str], str]:
    """根据 target_type 解析并验证目标。SELF 时锁定出牌者自身；其余类型要求 passed_targets 恰好 1 个元素作为锚点。"""

    # SELF：目标锁定为出牌者本人，无需目标名，传入的目标列表被忽略。
    if target_type == TargetType.SELF:
        return [actor_entity.name], ""

    # 其余类型要求 passed_targets 恰好 1 个元素作为锚点
    if len(passed_targets) != 1:
        return (
            [],
            f"{target_type.value.upper()} 目标数量必须为 1（作为目标/阵营锚点），实际收到 {len(passed_targets)} 个",
        )

    # 获取锚点目标名称（passed_targets 中的唯一元素）
    anchor_target_name = passed_targets[0]

    match target_type:

        case TargetType.SINGLE:

            # 获取当前场景中所有存活角色的名称集合
            alive_names = {
                e.name for e in get_alive_actors_in_stage(dbg_game, actor_entity)
            }

            # SINGLE 类型目标必须在当前场景存活角色列表中
            if anchor_target_name not in alive_names:
                return (
                    [],
                    f"目标 '{anchor_target_name}' 不在当前场景存活角色列表中: {sorted(alive_names)}",
                )

            # 返回 SINGLE 类型目标的锚点名称作为目标列表
            return [anchor_target_name], ""

        case TargetType.ALL:

            # 获取阵营。
            camp_members, err = _expand_camp_members(
                anchor_target_name, actor_entity, dbg_game
            )

            # 如果获取阵营成员失败，返回错误
            if err:
                return [], err

            # 如果阵营当前无存活角色，返回错误
            if not camp_members:
                return [], "ALL：锚点所在阵营当前无存活角色"

            # 返回阵营中所有存活角色的名称列表作为目标列表
            return [e.name for e in camp_members], ""

        case TargetType.SPREAD:

            # 获取阵营。
            camp_members, err = _expand_camp_members(
                anchor_target_name, actor_entity, dbg_game
            )

            # 如果获取阵营成员失败，返回错误
            if err:
                return [], err

            # 如果阵营当前无存活角色，返回错误
            if not camp_members:
                return [], "SPREAD：锚点所在阵营当前无存活角色"

            # 每次命中独立随机落到阵营存活角色之一：可重复、可有人一次都没中，
            # 不做「每人至少一次」的保底（命中分配就是击数的直接随机结果）。
            spread_targets = random.choices(camp_members, k=hit_count)

            # 返回最终的 SPREAD 类型目标列表
            return [e.name for e in spread_targets], ""

        case _:
            assert False, f"未知的目标类型：{target_type}"
