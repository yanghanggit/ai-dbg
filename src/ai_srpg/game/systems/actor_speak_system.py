"""角色说话：把他说的话发给同一处能听见的人。

据点内是局部广播（在场者），站在战场上则按一格距离扩散。
"""

from typing import Dict, List, final, override

from ...entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ...models import ActorComponent, ActorSpeakAction, NoneEvent
from ..context import SRPGGame
from .stage_broadcast_mixin import StageBroadcastMixin


@final
class ActorSpeakSystem(ReactiveProcessor, StageBroadcastMixin):
    """消费 ``ActorSpeakAction``：把话广播出去。"""

    ##########################################################################################
    def __init__(self, game: SRPGGame) -> None:
        ReactiveProcessor.__init__(self, game)
        StageBroadcastMixin.__init__(self, game)

    ##########################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(all_of=[ActorSpeakAction, ActorComponent]): GroupEvent.ADDED}

    ##########################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        """只处理仍挂着动作的角色。"""
        return entity.has(ActorComponent, ActorSpeakAction)

    ##########################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        for entity in sorted(entities, key=lambda item: item.index):
            content = entity.get(ActorSpeakAction).content
            self.broadcast_from_actor(
                entity,
                NoneEvent(message=f"{entity.name}说：{content}"),
                exclude_entities={entity},
            )


###############################################################################
__all__ = ["ActorSpeakSystem"]
