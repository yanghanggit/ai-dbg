"""战斗回合完成判定系统：存活角色全部交出行动权即结束本回合。"""

from typing import Final, final, override

from loguru import logger

from ..entitas import Entity, ExecuteProcessor
from ..game.combat import get_alive_actors_in_stage
from ..game.combat.state import (
    combat_round_view,
    latest_combat_round,
)
from ..game.context import DBGGame
from ..game.dungeon import (
    current_combat_entity,
    current_dungeon_combat,
    is_current_room_dungeon_combat,
)
from ..game.entities import (
    get_player_entity,
)
from ..models import CombatRoundComponent


###############################################################################################################################################
@final
class CombatRoundCompletionSystem(ExecuteProcessor):
    """战斗回合完成判定系统"""

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ############################################################################################################
    @override
    async def execute(self) -> None:
        # 守卫①：战斗未进行中 → 跳过
        if not is_current_room_dungeon_combat(self._game):
            return
        if not current_dungeon_combat(self._game).is_ongoing:
            return

        combat_entity = current_combat_entity(self._game)
        latest_round = latest_combat_round(self._game, combat_entity)

        # 守卫②：无回合，或回合已标记完成 → 跳过
        if latest_round is None:
            return
        round_view = combat_round_view(self._game, latest_round)
        if round_view.is_completed:
            return

        # 守卫③：init round（无行动槽） → 跳过
        if not round_view.action_order:
            return

        # 获取本场景所有存活角色
        player_entity = get_player_entity(self._game)
        assert player_entity is not None, "player_entity is None"

        # 获取本场景所有存活角色（不包括已死亡的角色）
        actors_in_stage = get_alive_actors_in_stage(self._game, player_entity)

        # 判断：所有存活角色均已 pass turn（completed_actors 是行动权推进的唯一依据，
        # 与 energy 是否耗尽无关；死亡角色已被 get_alive_actors_in_stage 过滤，不会阻塞回合结束）
        completed = set(round_view.completed_actors)
        all_passed = all(actor.name in completed for actor in actors_in_stage)

        if all_passed:
            self._mark_round_completed(latest_round)
            logger.info(
                f"回合完成：所有存活角色均已 pass turn，is_completed = True（action_order={round_view.action_order}）"
            )

    ############################################################################################################
    def _mark_round_completed(self, round_entity: Entity) -> None:
        """标记回合完成。"""
        round_comp = round_entity.get(CombatRoundComponent)
        round_entity.replace(
            CombatRoundComponent,
            round_comp.name,
            round_comp.combat_name,
            round_comp.index,
            True,
            round_comp.draw_completed,
        )
