"""事件投递原语：把一条事件写进指定实体的记忆，并发布到游戏的事件出口。

「向哪个范围投递」属于系统层，由 ``game/systems`` 里的 mixin 负责解析；这里只管
投递本身，不认识舞台、角色与广播范围。
"""

from typing import Any, Dict, Optional, Set

from ...entitas import Entity
from ...models import AnyAgentEvent, HumanMessage
from ..context import SRPGGame
from ..memory.access import add_human_message


#################################################################################################################################################
def notify_entities(
    srpg_game: SRPGGame,
    entities: Set[Entity],
    agent_event: AnyAgentEvent,
    *,
    broadcast_stage: Optional[str] = None,
) -> None:
    """向指定实体投递事件消息，并发布到游戏的事件出口。

    ``broadcast_stage`` 只由全舞台广播传入，用于在记忆里标记广播范围；私发不传，
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
