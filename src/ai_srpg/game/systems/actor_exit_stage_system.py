"""出城：从据点回到战场上据点所在的那一格，无论在里面走得多深。

据点对外只是一个节点，所以出城不需要「先走到城门」——落点固定是据点根的格。
"""

from typing import Dict, List, final, override

from ...entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ...models import ActorComponent, ActorExitStageAction, PositionComponent
from ..context import SRPGGame
from ..entities.queries import get_cell, get_global_stage, get_settlement, is_on_map
from .location_change_mixin import LocationChangeMixin


@final
class ActorExitStageSystem(ReactiveProcessor, LocationChangeMixin):
    """消费 ``ActorExitStageAction``：摘掉据点归属，站到据点所在格。"""

    ##########################################################################################
    def __init__(self, game: SRPGGame) -> None:
        ReactiveProcessor.__init__(self, game)
        LocationChangeMixin.__init__(self, game)

    ##########################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {
            Matcher(all_of=[ActorExitStageAction, ActorComponent]): GroupEvent.ADDED
        }

    ##########################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        """只处理仍挂着动作、且在据点里的角色。"""
        return entity.has(ActorComponent, ActorExitStageAction) and not is_on_map(
            self._game, entity
        )

    ##########################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        for entity in sorted(entities, key=lambda item: item.index):
            self._exit(entity)

    ##########################################################################################
    def _exit(self, entity: Entity) -> None:
        settlement = get_settlement(self._game, entity)
        assert settlement is not None, f"{entity.name} 在据点里却没有据点根"
        global_stage = get_global_stage(self._game, settlement.name)
        _, (x, y) = get_cell(self._game, entity)

        self.announce_departure(entity, location=settlement, from_label=settlement.name)

        entity.replace(ActorComponent, global_stage.name)
        entity.replace(PositionComponent, x, y)

        to_label = f"{global_stage.name}({x},{y})"
        self.announce_arrival(entity, location=global_stage, to_label=to_label)
        self.record_journey(entity, from_label=settlement.name, to_label=to_label)


###############################################################################
__all__ = ["ActorExitStageSystem"]
