"""确定性战斗结算：伤害/格挡计算、结果广播与 HP 落库。"""

from dataclasses import dataclass
from typing import Dict

from loguru import logger

from ..entitas import Entity
from ..game.combat import compute_character_stats, set_character_hp
from ..game.context import DBGGame
from ..game.dungeon import current_dungeon_combat
from ..game.entities import get_entity_by_name
from ..game.memory import add_human_message
from ..game.messaging import broadcast_to_stage
from ..models import CombatArbitrationEvent, HumanMessage
from ..utils import prompt_builder

###########################################################################################################################################
MINUS = "−"  # U+2212，与既有 combat_log 风格一致


###########################################################################################################################################
@dataclass(frozen=True)
class DamageResult:
    """一次「承伤」结算结果。`total` 即目标 HP 的净减少量。"""

    hits: int
    per_hit: int
    total: int
    new_hp: int
    expr: str


###########################################################################################################################################
def compute_damage(
    *,
    base_damage: int,
    hits: int,
    block: int,
    old_hp: int,
    max_hp: int,
) -> DamageResult:
    """按「每击 damage 减目标总格挡」结算承伤。

    `每击伤害 = max(0, damage − block)`，逐击求和；负 damage / block 按 0 处理。
    """
    base_damage = max(0, int(base_damage))
    hits = max(0, int(hits))
    block = max(0, int(block))
    per_hit = max(0, base_damage - block)
    total = per_hit * hits
    new_hp = max(0, min(int(old_hp) - total, int(max_hp)))
    expr = f"{base_damage}{MINUS}{block}=每击{per_hit} ×{hits}击={total}"
    return DamageResult(
        hits=hits, per_hit=per_hit, total=total, new_hp=new_hp, expr=expr
    )


###########################################################################################################################################
def build_empty_combat_log() -> str:
    """本次结算没有产生 HP 变化时的数据日志占位。"""
    return "本回合无 HP 变化"


###########################################################################################################################################
@prompt_builder
def build_stats_update_notification(final_hp: int, max_hp: int) -> str:
    """发给受影响角色的「生命值已更新」通知。"""
    return f"""# 你的生命值已更新

当前HP: {final_hp}/{max_hp}"""


###########################################################################################################################################
@prompt_builder
def build_resolution_broadcast(
    round_number: int, title_label: str, narrative: str, combat_log: str
) -> str:
    """静态结算的广播消息生成器。"""
    return f"""# 第 {round_number} 回合 · {title_label}

## 演出

{narrative}

## 数据日志

{combat_log}"""


###########################################################################################################################################
def apply_combat_resolution(
    game: DBGGame,
    stage_entity: Entity,
    *,
    title_label: str,
    narrative: str,
    combat_log: str,
    hp_changes: Dict[str, int],
) -> None:
    """落库一次静态结算：全场景广播 + HP 更新 + 生命值通知。"""
    current_round_number = len(current_dungeon_combat(game).rounds or [])
    broadcast_to_stage(
        game,
        entity=stage_entity,
        agent_event=CombatArbitrationEvent(
            message=build_resolution_broadcast(
                current_round_number, title_label, narrative, combat_log
            ),
            stage=stage_entity.name,
            combat_log=combat_log,
            narrative=narrative,
        ),
        exclude_entities={stage_entity},
    )

    for entity_name, hp in hp_changes.items():
        entity = get_entity_by_name(game, entity_name)
        assert entity is not None, f"无法找到 hp_changes 中的实体: {entity_name}"
        old_hp = compute_character_stats(entity).hp
        after_stats = set_character_hp(entity, int(hp))
        logger.info(
            f"更新 {entity_name} HP: {old_hp} → {after_stats.hp}/{after_stats.max_hp}"
        )
        add_human_message(
            game,
            entity,
            HumanMessage(
                content=build_stats_update_notification(
                    after_stats.hp, after_stats.max_hp
                ),
                stats_update=f"{old_hp}->{after_stats.hp}",
            ),
        )
