"""进城：从据点所在的那一格走进去。落点永远是据点根，与内部多深无关。

据点对外只是一个节点，所以进城只有一种结果：``current_stage`` 变成据点根，
自己的坐标被摘掉。
"""

from typing import Dict, List, final, override

from loguru import logger

from ...entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ...models import ActorComponent, ActorEnterStageAction, PositionComponent
from ..context import SRPGGame
from ..entities.queries import (
    get_cell,
    get_stage_at_cell,
    get_stage_entity,
    is_on_map,
)
from .location_change_mixin import LocationChangeMixin


@final
class ActorEnterStageSystem(ReactiveProcessor, LocationChangeMixin):
    """消费 ``ActorEnterStageAction``：站在城下才能进城。"""

    ##########################################################################################
    def __init__(self, game: SRPGGame) -> None:
        ReactiveProcessor.__init__(self, game)
        LocationChangeMixin.__init__(self, game)

    ##########################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {
            Matcher(all_of=[ActorEnterStageAction, ActorComponent]): GroupEvent.ADDED
        }

    ##########################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        """只处理仍挂着动作、且站在地图上的角色。"""
        return entity.has(ActorComponent, ActorEnterStageAction) and is_on_map(
            self._game, entity
        )

    ##########################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        for entity in sorted(entities, key=lambda item: item.index):
            self._enter(entity)

    ##########################################################################################
    def _enter(self, entity: Entity) -> None:
        action = entity.get(ActorEnterStageAction)
        stage_entity = get_stage_entity(self._game, action.stage_name)
        if stage_entity is None:
            logger.warning(f"{entity.name} 要进的据点不存在: {action.stage_name}")
            return

        global_stage, cell = get_cell(self._game, entity)
        here = get_stage_at_cell(self._game, global_stage, cell)
        if here is None or here.name != stage_entity.name:
            logger.warning(
                f"{entity.name} 不在 {stage_entity.name} 所在的格子 {cell}，不能进城"
            )
            return

        settlement = get_stage_entity(self._game, stage_entity.name)
        assert settlement is not None
        from_label = self.map_label(entity)
        self.announce_departure(entity, location=global_stage, from_label=from_label)

        entity.replace(ActorComponent, settlement.name)
        if entity.has(PositionComponent):
            entity.remove(PositionComponent)

        self.announce_arrival(entity, location=settlement, to_label=settlement.name)
        self.record_journey(entity, from_label=from_label, to_label=settlement.name)


###############################################################################
__all__ = ["ActorEnterStageSystem"]
