"""战斗行动槽状态迁移 mixin：当前槽选择、推进与死亡标记。"""

from typing import Optional

from ..entitas import Entity
from ..game.combat.state import (
    combat_rounds,
    combat_turns,
    current_turn_for_round,
)
from ..game.entities import get_actor_entity, get_entity_by_name
from ..models import (
    CombatTurnComponent,
    CombatTurnStatus,
    CurrentCombatTurnComponent,
    DeathComponent,
)
from .mixin_protocol import SystemMixinProtocol


###############################################################################################################################################
class CombatTurnStateMixin(SystemMixinProtocol):
    """为战斗系统提供行动槽状态迁移能力。

    当前槽选择、向下一槽推进、死亡槽标记都依赖系统持有的 ``DBGGame``，
    且会直接改写 ECS 实体；因此通过 mixin 让使用方以 ``self._xxx`` 调用，
    避免领域层残留仅供系统消费的 POST 封装。
    """

    ###############################################################################################################################################
    def _set_current_turn(self, turn_entity: Entity) -> None:
        """把指定行动槽设为当前行动槽；同一战斗只保留一个当前槽。"""
        turn_comp = turn_entity.get(CombatTurnComponent)
        assert (
            turn_comp.status == CombatTurnStatus.PENDING
        ), f"已结束的行动槽不能成为当前行动槽: {turn_entity.name}"

        combat_entity = get_entity_by_name(self._game, turn_comp.combat_name)
        assert combat_entity is not None, f"找不到战斗实体: {turn_comp.combat_name}"
        for round_entity in combat_rounds(self._game, combat_entity):
            for existing_turn in combat_turns(self._game, round_entity):
                if existing_turn.has(CurrentCombatTurnComponent):
                    existing_turn.remove(CurrentCombatTurnComponent)

        turn_entity.replace(CurrentCombatTurnComponent, turn_entity.name)

    ###############################################################################################################################################
    def _advance_current_turn(self, round_entity: Entity) -> Optional[Entity]:
        """把当前行动槽推进到下一个可用槽；没有可用槽时移除当前标记。"""
        turn_entities = combat_turns(self._game, round_entity)
        current_turn = current_turn_for_round(self._game, round_entity)
        start_index = 0
        if current_turn is not None:
            start_index = turn_entities.index(current_turn) + 1

        for turn_entity in turn_entities[start_index:]:
            turn_comp = turn_entity.get(CombatTurnComponent)
            if turn_comp.status != CombatTurnStatus.PENDING:
                continue

            actor_entity = get_actor_entity(self._game, turn_comp.actor_name)
            assert (
                actor_entity is not None
            ), f"找不到行动槽角色实体: {turn_comp.actor_name}"
            if actor_entity.has(DeathComponent):
                self._mark_turn_dead(turn_entity)
                continue

            self._set_current_turn(turn_entity)
            return turn_entity

        if current_turn is not None:
            current_turn.remove(CurrentCombatTurnComponent)
        return None

    ###############################################################################################################################################
    def _mark_turn_dead(self, turn_entity: Entity) -> None:
        """标记行动槽对应的角色已死亡，后续推进应跳过它。"""
        turn_comp = turn_entity.get(CombatTurnComponent)
        turn_entity.replace(
            CombatTurnComponent,
            turn_comp.name,
            turn_comp.combat_name,
            turn_comp.round_name,
            turn_comp.actor_name,
            turn_comp.order_index,
            CombatTurnStatus.DEAD,
            turn_comp.energy,
        )
