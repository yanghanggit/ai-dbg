"""位置变化的告知：旧处看见他走、新处看见他来、他自己记得这条路线。

调用顺序即语义：离开按「此刻所在处」投递，必须在改组件之前发；到达按「新的所在处」，
之后发。地图与据点的投递对象不同——地图只记在自己身上。
"""

from ...entitas import Entity
from ...models import GlobalStageComponent, HumanMessage, NoneEvent
from ..entities.queries import get_cell, resolve_stage_entity
from ..memory import add_human_message
from .stage_broadcast_mixin import StageBroadcastMixin


class LocationChangeMixin(StageBroadcastMixin):
    """把一次位置变化说给三处听：旧处、新处、他自己。"""

    ############################################################################################################
    def announce_departure(
        self, entity: Entity, *, location: Entity, from_label: str
    ) -> None:
        """旧处的在场者看见他离开；调用时角色还在原地。"""
        self.broadcast_at_location(
            location,
            NoneEvent(message=f"{entity.name}离开了{from_label}。"),
            exclude_entities={entity},
        )

    ############################################################################################################
    def announce_arrival(
        self, entity: Entity, *, location: Entity, to_label: str
    ) -> None:
        """新处的在场者看见他到来；调用时组件已经改好。"""
        self.broadcast_at_location(
            location,
            NoneEvent(message=f"{entity.name}来到了{to_label}。"),
            exclude_entities={entity},
        )

    ############################################################################################################
    def record_journey(self, entity: Entity, *, from_label: str, to_label: str) -> None:
        """他自己记住从哪儿走到哪儿：别人的「他来了」不能替他回答这件事。"""
        add_human_message(
            self._game,
            entity,
            HumanMessage(content=f"你从{from_label}走到{to_label}。"),
        )

    ############################################################################################################
    def map_label(self, entity: Entity) -> str:
        """地图上的位置说法：「全局舞台(x,y)」；据点里用区域名。"""
        stage_entity = resolve_stage_entity(self._game, entity)
        assert stage_entity is not None, f"{entity.name} 无所在舞台"
        if not stage_entity.has(GlobalStageComponent):
            return stage_entity.name
        _, (x, y) = get_cell(self._game, entity)
        return f"{stage_entity.name}({x},{y})"


###############################################################################
__all__ = ["LocationChangeMixin"]
