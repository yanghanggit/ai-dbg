"""战斗状态转换系统：战斗结束后将战斗状态从 COMPLETE 转换为 POST_COMBAT。"""

from typing import Final, final

from loguru import logger
from overrides import override

from ..entitas import Entity, ExecuteProcessor
from ..game.context import SRPGGame
from ..game.dungeon import (
    current_combat_entity,
    current_dungeon_combat,
    is_current_room_dungeon_combat,
)
from ..models import CombatResult, CombatState, CombatStateComponent


#######################################################################################################################################
@final
class CombatPostCombatTransitionSystem(ExecuteProcessor):
    """战斗结束后转换战斗状态：COMPLETE -> POST_COMBAT。"""

    def __init__(self, game: SRPGGame) -> None:
        self._game: Final[SRPGGame] = game

    #######################################################################################################################################
    @override
    async def execute(self) -> None:
        """每帧检查战斗是否结束；结束则将战斗状态转换为战后阶段。"""

        if not is_current_room_dungeon_combat(self._game):
            return
        combat = current_dungeon_combat(self._game)
        if not combat.is_combat_completed:
            # 战斗未结束（或已处于战后阶段），无需转换。
            return

        assert combat.is_won or combat.is_lost, "战斗结果状态异常！"

        logger.info("战斗结束，转换战斗状态：COMPLETE -> POST_COMBAT")
        self._transition_to_post_combat(current_combat_entity(self._game))

    #######################################################################################################################################
    def _transition_to_post_combat(self, combat_entity: Entity) -> None:
        """将战斗状态从 COMPLETE 转换为 POST_COMBAT。"""
        state_comp = combat_entity.get(CombatStateComponent)
        assert state_comp.result in (CombatResult.WIN, CombatResult.LOSE)
        assert state_comp.state == CombatState.COMPLETE
        combat_entity.replace(
            CombatStateComponent,
            state_comp.name,
            state_comp.room_name,
            CombatState.POST_COMBAT,
            state_comp.result,
            state_comp.retreated,
        )


#######################################################################################################################################
