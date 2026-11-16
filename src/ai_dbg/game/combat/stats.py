"""角色战斗属性、HP 与 energy。"""

from ...entitas import Entity
from ...models import (
    ActorComponent,
    CharacterStats,
    CharacterStatsComponent,
    CombatTurnComponent,
    DeathComponent,
    EquippedGearComponent,
    HandComponent,
    compute_effective_stats,
    compute_hand_block,
)


def compute_character_stats(entity: Entity) -> CharacterStats:
    """返回角色的基础属性（CharacterStats），不含手牌 block 加成。"""
    assert entity.has(ActorComponent), f"{entity.name} 缺少 ActorComponent"
    assert entity.has(
        CharacterStatsComponent
    ), f"{entity.name} 缺少 CharacterStatsComponent"

    stats_comp = entity.get(CharacterStatsComponent)
    equipped_gear = (
        entity.get(EquippedGearComponent) if entity.has(EquippedGearComponent) else None
    )
    return compute_effective_stats(stats_comp.stats, equipped_gear)


def compute_character_hand_block(entity: Entity) -> int:
    """计算角色手牌提供的总格挡（block 之和）。"""
    hand = entity.get(HandComponent) if entity.has(HandComponent) else None
    return compute_hand_block(hand)


def set_character_hp(entity: Entity, hp: int) -> CharacterStats:
    """设置角色的当前 HP，自动 clamp 至 [0, max_hp]。"""
    assert entity.has(ActorComponent), f"{entity.name} 缺少 ActorComponent"
    assert entity.has(
        CharacterStatsComponent
    ), f"{entity.name} 缺少 CharacterStatsComponent"

    stats_comp = entity.get(CharacterStatsComponent)
    max_hp = compute_character_stats(entity).max_hp
    clamped = max(0, min(hp, max_hp))
    entity.replace(
        CharacterStatsComponent,
        stats_comp.name,
        stats_comp.stats.model_copy(update={"hp": clamped}),
    )

    return compute_character_stats(entity)


def mark_dead(entity: Entity) -> CharacterStats:
    """将角色标记为战败：挂载 DeathComponent。

    战死 / 超时判负 / 撤退均视为一次战败，统一走此入口。
    """
    assert entity.has(ActorComponent), f"{entity.name} 缺少 ActorComponent"
    assert entity.has(
        CharacterStatsComponent
    ), f"{entity.name} 缺少 CharacterStatsComponent"

    entity.replace(DeathComponent, entity.name)

    return compute_character_stats(entity)


def get_turn_energy(turn_entity: Entity) -> int:
    """获取行动槽实体当前剩余行动力。"""
    turn_comp = turn_entity.get(CombatTurnComponent)
    return turn_comp.energy


def consume_turn_energy(turn_entity: Entity, amount: int = 1) -> None:
    """消耗行动槽实体指定点数的 energy。"""
    turn_comp = turn_entity.get(CombatTurnComponent)
    assert (
        turn_comp.energy > 0
    ), f"{turn_entity.name} 能量不足！当前 energy={turn_comp.energy}"
    turn_entity.replace(
        CombatTurnComponent,
        turn_comp.name,
        turn_comp.combat_name,
        turn_comp.round_name,
        turn_comp.actor_name,
        turn_comp.order_index,
        turn_comp.status,
        max(0, turn_comp.energy - amount),
    )
