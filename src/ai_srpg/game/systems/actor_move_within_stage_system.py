"""城内移动：在据点内部从一个区域走到相邻区域。

可去的是子区域与父区域；父区域是全局舞台时不算——那是出城。
"""

from typing import Dict, List, final, override

from loguru import logger

from ...entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ...models import ActorComponent, ActorMoveWithinStageAction
from ..context import SRPGGame
from ..entities.queries import get_adjacent_stages, is_on_map, resolve_stage_entity
from .location_change_mixin import LocationChangeMixin


@final
class ActorMoveWithinStageSystem(ReactiveProcessor, LocationChangeMixin):
    """消费 ``ActorMoveWithinStageAction``：校验相邻区域，改所在区域。"""

    ##########################################################################################
    def __init__(self, game: SRPGGame) -> None:
        ReactiveProcessor.__init__(self, game)
        LocationChangeMixin.__init__(self, game)

    ##########################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {
            Matcher(
                all_of=[ActorMoveWithinStageAction, ActorComponent]
            ): GroupEvent.ADDED
        }

    ##########################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        """只处理仍挂着动作、且在据点里的角色。"""
        return entity.has(ActorComponent, ActorMoveWithinStageAction) and not is_on_map(
            self._game, entity
        )

    ##########################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        for entity in sorted(entities, key=lambda item: item.index):
            self._move(entity)

    ##########################################################################################
    def _move(self, entity: Entity) -> None:
        destination = entity.get(ActorMoveWithinStageAction).destination
        reachable = {stage.name for stage in get_adjacent_stages(self._game, entity)}
        if destination not in reachable:
            logger.warning(
                f"{entity.name} 只能在据点内移动到相邻区域，忽略目标 {destination!r}"
            )
            return

        from_stage = resolve_stage_entity(self._game, entity)
        assert from_stage is not None, f"{entity.name} 无所在舞台"
        target = self._stage_by_name(destination)

        self.announce_departure(entity, location=from_stage, from_label=from_stage.name)

        entity.replace(ActorComponent, target.name)

        self.announce_arrival(entity, location=target, to_label=target.name)
        self.record_journey(entity, from_label=from_stage.name, to_label=target.name)

    ##########################################################################################
    def _stage_by_name(self, stage_name: str) -> Entity:
        from ..entities.queries import get_stage_entity

        stage_entity = get_stage_entity(self._game, stage_name)
        assert stage_entity is not None, f"找不到舞台实体: {stage_name}"
        return stage_entity


###############################################################################
__all__ = ["ActorMoveWithinStageSystem"]
