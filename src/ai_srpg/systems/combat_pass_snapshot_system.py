"""战斗 pass 快照系统：在动作阶段入口冻结当前行动槽，并在 cleanup 阶段清除。"""

from typing import Final, final, override

from ..entitas import CleanupProcessor, ExecuteProcessor, Matcher
from ..game.context import SRPGGame
from ..game.dungeon import (
    current_combat_entity,
    current_combat_turn_entity,
    current_dungeon_combat,
    is_current_room_dungeon_combat,
)
from ..models import (
    CombatPassSnapshotComponent,
    CombatTurnComponent,
    CombatTurnStatus,
)


###################################################################################################################################################################
@final
class CombatPassSnapshotSystem(ExecuteProcessor, CleanupProcessor):
    """每个 pass 在动作阶段入口建立当前行动槽快照，pass 结束后兜底清除。

    快照不是行动权的权威来源；行动权仍由 ``CurrentCombatTurnComponent`` 决定。
    它只用于让决策与动作系统在同一次 pass 内共享同一个行动者。
    """

    def __init__(self, game: SRPGGame) -> None:
        self._game: Final[SRPGGame] = game

    ###############################################################################################################################################################
    @override
    async def execute(self) -> None:
        self._clear_snapshot()
        self._create_snapshot()

    ###############################################################################################################################################################
    @override
    def cleanup(self) -> None:
        self._clear_snapshot()

    ###############################################################################################################################################################
    def _clear_snapshot(self) -> None:
        """移除所有残留快照；幂等，供正常与失败路径共用。"""
        snapshot_entities = self._game.ecs.get_group(
            Matcher(all_of=[CombatPassSnapshotComponent])
        ).entities.copy()
        for entity in snapshot_entities:
            entity.remove(CombatPassSnapshotComponent)

    ###############################################################################################################################################################
    def _create_snapshot(self) -> None:
        """若当前处于可行动的战斗阶段，则冻结当前行动槽；否则保持无快照。"""
        if not is_current_room_dungeon_combat(self._game):
            return
        if not current_dungeon_combat(self._game).is_ongoing:
            return

        turn_entity = current_combat_turn_entity(self._game)
        if turn_entity is None:
            return

        turn_comp = turn_entity.get(CombatTurnComponent)
        if turn_comp.status != CombatTurnStatus.PENDING:
            raise ValueError(
                f"当前行动槽 {turn_entity.name} 已结束，不能建立 pass 快照"
            )

        combat_entity = current_combat_entity(self._game)
        turn_entity.replace(
            CombatPassSnapshotComponent,
            combat_entity.name,
            turn_comp.round_name,
            turn_entity.name,
            turn_comp.actor_name,
        )
