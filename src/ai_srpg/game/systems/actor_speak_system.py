"""角色说话：把话告诉同一个据点区域里的人。

说话是「场所里的事」：地图不是场所，所以站在战场上的角色不开口。
"""

from typing import Dict, List, final, override

from ...entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ...models import ActorComponent, ActorSpeakAction, NoneEvent
from ..context import SRPGGame
from ..entities.queries import is_on_map, resolve_stage_entity
from .stage_broadcast_mixin import StageBroadcastMixin


@final
class ActorSpeakSystem(ReactiveProcessor, StageBroadcastMixin):
    """消费 ``ActorSpeakAction``：在所在区域里广播这句话。"""

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
        """只处理仍挂着动作、且不在战场上的角色。"""
        return entity.has(ActorComponent, ActorSpeakAction) and not is_on_map(
            self._game, entity
        )

    ##########################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        for entity in sorted(entities, key=lambda item: item.index):
            stage_entity = resolve_stage_entity(self._game, entity)
            assert stage_entity is not None, f"{entity.name} 无所在舞台"
            content = entity.get(ActorSpeakAction).content
            self.broadcast_at_location(
                stage_entity,
                NoneEvent(message=f"{entity.name}说：{content}"),
                exclude_entities={entity},
            )


###############################################################################
__all__ = ["ActorSpeakSystem"]
