"""角色等待：告诉同一处的在场者他没有动。

等待也有信息量——「什么都没发生」与「没人在」是两件事。
"""

from typing import Dict, List, final, override

from ...entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ...models import ActorComponent, ActorWaitAction, NoneEvent
from ..context import SRPGGame
from .stage_broadcast_mixin import StageBroadcastMixin


@final
class ActorWaitSystem(ReactiveProcessor, StageBroadcastMixin):
    """消费 ``ActorWaitAction``：广播一条「留在原地」。"""

    ##########################################################################################
    def __init__(self, game: SRPGGame) -> None:
        ReactiveProcessor.__init__(self, game)
        StageBroadcastMixin.__init__(self, game)

    ##########################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(all_of=[ActorWaitAction, ActorComponent]): GroupEvent.ADDED}

    ##########################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        """只处理仍挂着动作的角色。"""
        return entity.has(ActorComponent, ActorWaitAction)

    ##########################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        for entity in sorted(entities, key=lambda item: item.index):
            self.broadcast_from_actor(
                entity,
                NoneEvent(message=f"{entity.name}留在原地。"),
                exclude_entities={entity},
            )


###############################################################################
__all__ = ["ActorWaitSystem"]
