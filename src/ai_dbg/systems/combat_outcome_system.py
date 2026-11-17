"""战斗结果判定系统：检测阵营全灭条件并结束战斗。"""

from typing import Final, Set, Type, final, override

from loguru import logger

from ..entitas import Component, Entity, ExecuteProcessor
from ..game.context import DBGGame
from ..game.dungeon import (
    current_combat_entity,
    current_dungeon_combat,
    is_current_room_dungeon_combat,
)
from ..game.entities import (
    get_actors_in_stage,
    get_player_entity,
)
from ..models import (
    CombatResult,
    CombatState,
    CombatStateComponent,
    DeathComponent,
    DiscardPileComponent,
    DrawPileComponent,
    HandComponent,
    MonsterComponent,
    PartyMemberComponent,
)


@final
class CombatOutcomeSystem(ExecuteProcessor):
    """
    战斗结果判定系统。
    """

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ########################################################################################################################################################################
    @override
    async def execute(self) -> None:
        """检测阵营全灭条件，调用 _complete_combat() 结束战斗；战斗未 ONGOING 时静默跳过。"""

        if not is_current_room_dungeon_combat(self._game):
            return
        if not current_dungeon_combat(self._game).is_ongoing:
            logger.debug("当前不在战斗阶段，无需判定战斗胜负")
            return  # 不是本阶段就直接返回

        logger.debug("判定战斗胜负：检查双方阵营存活情况")

        combat_result = self._determine_combat_result()
        if combat_result == CombatResult.NONE:
            logger.debug("战斗尚未结束，继续进行")
            return

        logger.info(f"战斗结束，结果: {combat_result}")

        # 推进战斗状态机（ONGOING -> COMPLETE），后续 pipeline 系统据此判断是否进入战后阶段
        self._complete_combat(current_combat_entity(self._game), combat_result)

        # 手牌清理与胜负通知由后续 CombatHandCleanupSystem / CombatResultNoticeSystem 统一处理

    ########################################################################################################################################################################
    def _complete_combat(self, combat_entity: Entity, result: CombatResult) -> None:
        """将战斗状态从 ONGOING 转换为 COMPLETE。"""
        state_comp = combat_entity.get(CombatStateComponent)
        assert state_comp.state == CombatState.ONGOING
        assert result in (CombatResult.WIN, CombatResult.LOSE)
        assert state_comp.result == CombatResult.NONE
        combat_entity.replace(
            CombatStateComponent,
            state_comp.name,
            state_comp.room_name,
            CombatState.COMPLETE,
            result,
            state_comp.retreated,
        )

    ########################################################################################################################################################################
    def _determine_combat_result(self) -> CombatResult:
        """根据当前战斗状态判断战斗结果。"""

        if self._is_player_side_eliminated():
            return CombatResult.LOSE
        elif self._is_enemy_side_eliminated():
            return CombatResult.WIN
        elif self._is_both_sides_cardless():
            return CombatResult.LOSE

        return CombatResult.NONE

    ########################################################################################################################################################################
    def _get_actors_in_stage(self) -> Set[Entity]:
        """返回当前场景内所有参战角色实体（含已死亡角色）。"""
        player_entity = get_player_entity(self._game)
        assert player_entity is not None, "Player entity should not be None."

        actors_in_stage = get_actors_in_stage(self._game, player_entity)
        assert len(actors_in_stage) > 0, f"entities with actions: {actors_in_stage}"
        return actors_in_stage

    ########################################################################################################################################################################
    def _is_side_eliminated(self, component_cls: Type[Component]) -> bool:
        """返回指定阵营（由 component_cls 标记）是否已全员带有 DeathComponent。"""
        actors_in_stage = self._get_actors_in_stage()

        members: Set[Entity] = set()
        defeated_members: Set[Entity] = set()

        for entity in actors_in_stage:

            if not entity.has(component_cls):
                continue

            members.add(entity)

            if entity.has(DeathComponent):
                defeated_members.add(entity)

        # 判断该阵营是否所有成员都已被击败（无成员时返回 False）
        return len(members) > 0 and len(defeated_members) >= len(members)

    ########################################################################################################################################################################
    def _is_player_side_eliminated(self) -> bool:
        """返回友方阵营（PartyMemberComponent）是否已全员带有 DeathComponent。"""
        return self._is_side_eliminated(PartyMemberComponent)

    ########################################################################################################################################################################
    def _is_enemy_side_eliminated(self) -> bool:
        """返回敌方阵营（MonsterComponent）是否已全员带有 DeathComponent。"""
        return self._is_side_eliminated(MonsterComponent)

    ########################################################################################################################################################################
    def _is_side_cardless(self, members: Set[Entity]) -> bool:
        """返回指定成员集合是否均无可用卡牌（DrawPile / Hand / DiscardPile 均为空）。"""
        if not members:
            return False
        return all(self._count_available_cards(entity) == 0 for entity in members)

    ########################################################################################################################################################################
    def _is_both_sides_cardless(self) -> bool:
        """返回双方阵营存活成员是否均无可用卡牌（平局破局条件）。"""
        actors_in_stage = self._get_actors_in_stage()

        alive_allies: Set[Entity] = set()
        alive_enemies: Set[Entity] = set()

        for entity in actors_in_stage:

            if entity.has(DeathComponent):
                continue

            if entity.has(PartyMemberComponent):
                alive_allies.add(entity)
            elif entity.has(MonsterComponent):
                alive_enemies.add(entity)

        return self._is_side_cardless(alive_allies) and self._is_side_cardless(
            alive_enemies
        )

    ########################################################################################################################################################################
    def _count_available_cards(self, entity: Entity) -> int:
        """统计实体 DrawPile + Hand + DiscardPile 三堆卡牌总数（不含 ExhaustPile）。"""
        total = 0
        if entity.has(DrawPileComponent):
            draw_pile = entity.get(DrawPileComponent)
            total += len(draw_pile.cards) + len(draw_pile.retained_cards)
        if entity.has(HandComponent):
            total += len(entity.get(HandComponent).cards)
        if entity.has(DiscardPileComponent):
            total += len(entity.get(DiscardPileComponent).cards)
        return total

    ########################################################################################################################################################################
