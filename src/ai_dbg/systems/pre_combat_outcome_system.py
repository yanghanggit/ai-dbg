"""战斗结果判定前的占位处理器，用于固定管线位置。"""

from typing import Final, final, override

from loguru import logger

from ..entitas import ExecuteProcessor
from ..game.combat import mark_dead
from ..game.context import DBGGame
from ..game.dungeon import (
    current_dungeon_combat_room,
    is_current_room_dungeon_combat,
)
from ..game.entities import (
    get_actors_in_stage,
    get_player_entity,
)
from ..models import (
    DeathComponent,
    PartyMemberComponent,
)

###############################################################################################################################################
# 战斗回合数上限：超过该值即强制友方失败
_MAX_COMBAT_ROUNDS = 20


###############################################################################################################################################
@final
class PreCombatOutcomeSystem(ExecuteProcessor):
    """战斗结果判定前系统。"""

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:
        if not is_current_room_dungeon_combat(self._game):
            return
        combat = current_dungeon_combat_room(self._game).combat

        # 状态守卫：仅在进行中的战斗里做超时处理
        if not combat.is_ongoing:
            return

        if len(combat.rounds) <= _MAX_COMBAT_ROUNDS:
            return

        player_entity = get_player_entity(self._game)
        assert player_entity is not None, "Player entity should not be None."

        actors_in_stage = get_actors_in_stage(self._game, player_entity)

        for entity in actors_in_stage:
            if entity.has(PartyMemberComponent) and not entity.has(DeathComponent):
                logger.info(
                    f"战斗超过 {_MAX_COMBAT_ROUNDS} 回合，强制友方失败：{entity.name}"
                )
                mark_dead(entity)
