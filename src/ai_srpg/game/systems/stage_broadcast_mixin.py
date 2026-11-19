"""局部舞台广播：一条事件投递给某个舞台及其在场角色。

只有局部舞台能这样广播。全局舞台（``GlobalStageComponent``）代表整张地图，没有
「在场者」这回事，向它广播等于把一条局部事件当成全局事实，因此直接拒绝。
"""

from typing import Optional, Set

from ...entitas import Entity
from ...models import AnyAgentEvent, GlobalStageComponent
from ..entities import get_actors_in_stage, resolve_stage_entity
from ..events.publish import notify_entities
from .system_mixin import SystemMixin


class StageBroadcastMixin(SystemMixin):
    """向局部舞台广播事件的 mixin；全局舞台不在其职责内。"""

    ############################################################################################################
    def broadcast_to_local_stage(
        self,
        entity: Entity,
        agent_event: AnyAgentEvent,
        *,
        exclude_entities: Optional[Set[Entity]] = None,
    ) -> None:
        """向 ``entity`` 所在舞台的全部角色与该舞台投递一条事件。

        ``exclude_entities`` 用于「说话者自己不必收到自己的话」这类场景。
        """
        stage_entity = resolve_stage_entity(self._game, entity)
        assert stage_entity is not None, f"{entity.name} 无所在舞台，无法广播"
        assert not stage_entity.has(
            GlobalStageComponent
        ), f"{stage_entity.name} 是全局舞台，不能用局部舞台广播"

        targets = (get_actors_in_stage(self._game, stage_entity) | {stage_entity}) - (
            exclude_entities or set()
        )
        notify_entities(
            self._game, targets, agent_event, broadcast_stage=stage_entity.name
        )


###############################################################################
__all__ = ["StageBroadcastMixin"]
