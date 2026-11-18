"""场景广播与定向通知。

两条投递路径只差「目标集合怎么来」与「是否标记广播范围」：投递与发布事件本身是
同一件事，因此统一由 ``notify_entities`` 完成，``broadcast_to_stage`` 只负责解析
目标。
"""

from typing import Any, Dict, Optional, Set

from ...entitas import Entity
from ...models import AnyAgentEvent, HumanMessage
from ..context import SRPGGame
from ..entities import get_actors_in_stage, resolve_stage_entity
from ..memory.access import add_human_message


#################################################################################################################################################
def broadcast_to_stage(
    srpg_game: SRPGGame,
    entity: Entity,
    agent_event: AnyAgentEvent,
    exclude_entities: Optional[Set[Entity]] = None,
) -> None:
    """向场景内所有角色与场景实体广播事件。"""
    stage_entity = resolve_stage_entity(srpg_game, entity)
    assert stage_entity is not None, f"{entity.name} 无所在场景，无法广播"

    excluded = exclude_entities or set()
    targets = (get_actors_in_stage(srpg_game, stage_entity) | {stage_entity}) - excluded
    notify_entities(srpg_game, targets, agent_event, broadcast_stage=stage_entity.name)


#################################################################################################################################################
def notify_entities(
    srpg_game: SRPGGame,
    entities: Set[Entity],
    agent_event: AnyAgentEvent,
    *,
    broadcast_stage: Optional[str] = None,
) -> None:
    """向指定实体投递事件消息，并发布到游戏的事件出口。

    ``broadcast_stage`` 只由全场景广播传入，用于在记忆里标记广播范围；私发不传，
    消息上就不会出现这个标记。
    """
    for entity in entities:
        # 只在广播时带上标记：``extra="allow"`` 会把它留在消息的额外属性里，
        # 传 None 会写进词表之外的「存在但为空」状态，因此按需展开
        extra: Dict[str, Any] = (
            {"broadcast_stage": broadcast_stage} if broadcast_stage is not None else {}
        )
        add_human_message(
            srpg_game,
            entity,
            HumanMessage(
                content=agent_event.message,
                agent_event=agent_event.type,
                **extra,
            ),
        )

    srpg_game.events.publish(agent_event)
