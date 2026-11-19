"""战场移动：在战役地图上走到相邻一格，只改坐标，不改变所在层。

走到据点所在的格子不算进城——那是兵临城下，进城要靠 ``enter``。
"""

from typing import Dict, List, final, override

from loguru import logger

from ...entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ...models import ActorComponent, ActorTravelAction, PositionComponent
from ..context import SRPGGame
from ..entities.action_rules import action_blocker
from ..entities.queries import get_cell
from .location_change_mixin import LocationChangeMixin


@final
class ActorTravelSystem(ReactiveProcessor, LocationChangeMixin):
    """消费 ``ActorTravelAction``：校验相邻、改坐标、说给三处听。"""

    ##########################################################################################
    def __init__(self, game: SRPGGame) -> None:
        ReactiveProcessor.__init__(self, game)
        LocationChangeMixin.__init__(self, game)

    ##########################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(all_of=[ActorTravelAction, ActorComponent]): GroupEvent.ADDED}

    ##########################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        """只处理仍挂着动作的角色：动作在处理的同一刻被消费。"""
        return entity.has(ActorComponent, ActorTravelAction)

    ##########################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        for entity in sorted(entities, key=lambda item: item.index):
            self._travel(entity)

    ##########################################################################################
    def _travel(self, entity: Entity) -> None:
        action = entity.get(ActorTravelAction)
        entity.remove(ActorTravelAction)
        blocker = action_blocker(self._game, entity, action)
        if blocker is not None:
            logger.warning(f"{entity.name} 的战场移动被拒绝: {blocker}")
            return

        target = (action.cell_x, action.cell_y)
        from_label = self.map_label(entity)
        map_entity = get_cell(self._game, entity)[0]
        self.announce_departure(entity, location=map_entity, from_label=from_label)

        entity.replace(PositionComponent, target[0], target[1])

        to_label = self.map_label(entity)
        self.announce_arrival(entity, location=map_entity, to_label=to_label)
        self.record_journey(entity, from_label=from_label, to_label=to_label)


###############################################################################
__all__ = ["ActorTravelSystem"]
