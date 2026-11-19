"""角色移动：走到战场上的相邻一格，有据点就进去，空地就站在格上。

一格一物是舞台的规则，不是人的：同一格里的据点只有一个，站在格上的人可以不止一个。
"""

from typing import Dict, List, final, override

from loguru import logger

from ...entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ...models import ActorComponent, ActorMoveAction, PositionComponent
from ..context import SRPGGame
from ..entities.queries import Exit, get_exits, get_global_stage, resolve_stage_entity
from .stage_transition_mixin import StageTransitionMixin


@final
class ActorMoveSystem(ReactiveProcessor, StageTransitionMixin):
    """消费 ``ActorMoveAction``：校验相邻、改位置、说给三处听。"""

    ##########################################################################################
    def __init__(self, game: SRPGGame) -> None:
        ReactiveProcessor.__init__(self, game)
        StageTransitionMixin.__init__(self, game)

    ##########################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(all_of=[ActorMoveAction, ActorComponent]): GroupEvent.ADDED}

    ##########################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        """只处理仍挂着动作的角色。"""
        return entity.has(ActorComponent, ActorMoveAction)

    ##########################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        for entity in sorted(entities, key=lambda item: item.index):
            self._move(entity)

    ##########################################################################################
    def _move(self, entity: Entity) -> None:
        action = entity.get(ActorMoveAction)
        exits = {(item.x, item.y): item for item in get_exits(self._game, entity)}
        target = exits.get((action.cell_x, action.cell_y))
        if target is None:
            # 只能走到相邻格：越界或隔空跳都不执行，角色留在原地
            logger.warning(
                f"{entity.name} 只能走到相邻的一格，忽略目标 ({action.cell_x},{action.cell_y})"
            )
            return

        from_label = self.location_label(entity)
        self.announce_departure(entity, from_label=from_label)
        self._relocate(entity, target)
        to_label = self.location_label(entity)
        self.announce_arrival(entity, to_label=to_label)
        self.record_journey(entity, from_label=from_label, to_label=to_label)

    ##########################################################################################
    def _relocate(self, entity: Entity, target: Exit) -> None:
        """进据点就摘掉自己的坐标，站空地就写下格子坐标。"""
        if target.stage is not None:
            entity.replace(ActorComponent, target.stage)
            if entity.has(PositionComponent):
                entity.remove(PositionComponent)
            return

        stage_entity = resolve_stage_entity(self._game, entity)
        assert stage_entity is not None, f"{entity.name} 无所在舞台"
        global_stage = get_global_stage(self._game, stage_entity.name)
        entity.replace(ActorComponent, global_stage.name)
        entity.replace(PositionComponent, target.x, target.y)


###############################################################################
__all__ = ["ActorMoveSystem"]
