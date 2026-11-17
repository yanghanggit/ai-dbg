"""战斗结果通知系统：战斗结束后，向所有参战者写入各自视角的胜负通知。"""

from typing import Final, final, override

from ..entitas import ExecuteProcessor
from ..game.context import DBGGame
from ..game.dungeon import (
    current_dungeon_combat,
    is_current_room_dungeon_combat,
)
from ..game.entities import (
    get_actors_in_stage,
    get_player_entity,
    resolve_stage_entity,
)
from ..game.memory import add_human_message
from ..models import (
    CombatResult,
    HumanMessage,
    PartyMemberComponent,
)
from ..utils import prompt_builder


########################################################################################################################################################################
@prompt_builder
def _build_combat_result_notification(stage_name: str, is_victory: bool) -> str:
    """生成写入 agent 记忆的战斗胜/败通知文本。"""
    result_text = "胜利" if is_victory else "失败"
    return f"# {stage_name}的战斗{result_text}！"


########################################################################################################################################################################
@final
class CombatResultNoticeSystem(ExecuteProcessor):
    """战斗结果通知系统：在战斗进入 COMPLETE 后广播一次胜负结果。"""

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ########################################################################################################################################################################
    @override
    async def execute(self) -> None:
        if not is_current_room_dungeon_combat(self._game):
            return

        combat = current_dungeon_combat(self._game)
        if not combat.is_combat_completed:
            return

        assert combat.is_won or combat.is_lost, "战斗结果状态异常！"
        self._notify_combat_result(combat.result)

    ########################################################################################################################################################################
    def _notify_combat_result(self, result: CombatResult) -> None:
        """向当前场景内所有参战者（含怪物）写入胜/败通知，附带 combat_outcome 参数。

        文本按各自阵营视角生成：队伍看 `CombatResult`，怪物看其反面。
        """

        player_entity = get_player_entity(self._game)
        assert player_entity is not None, "Player entity should not be None."

        combat_stage_entity = resolve_stage_entity(self._game, player_entity)
        assert (
            combat_stage_entity is not None
        ), "Player's stage entity should not be None."

        actors_in_stage = get_actors_in_stage(self._game, player_entity)
        assert len(actors_in_stage) > 0, f"entities with actions: {actors_in_stage}"

        for entity in actors_in_stage:
            is_victory = (
                result == CombatResult.WIN
                if entity.has(PartyMemberComponent)
                else result == CombatResult.LOSE
            )
            add_human_message(
                self._game,
                entity,
                HumanMessage(
                    content=_build_combat_result_notification(
                        combat_stage_entity.name, is_victory
                    ),
                    combat_outcome=combat_stage_entity.name,
                ),
            )
