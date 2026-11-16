"""场景广播与定向通知。"""

from typing import Optional, Set

from ..entitas import Entity
from ..models import AnyAgentEvent, HumanMessage
from .dbg_game import DBGGame
from .game_entities import get_actors_in_stage, resolve_stage_entity
from .game_memory import add_human_message


#################################################################################################################################################
def broadcast_to_stage(
    dbg_game: DBGGame,
    entity: Entity,
    agent_event: AnyAgentEvent,
    exclude_entities: Optional[Set[Entity]] = None,
) -> None:
    """向场景内所有角色与场景实体广播事件。"""
    stage_entity = resolve_stage_entity(dbg_game, entity)
    assert stage_entity is not None, f"{entity.name} 无所在场景，无法广播"

    excluded = exclude_entities or set()
    targets = (get_actors_in_stage(dbg_game, stage_entity) | {stage_entity}) - excluded
    for target in targets:
        add_human_message(
            dbg_game,
            target,
            HumanMessage(
                content=agent_event.message,
                agent_event=agent_event.type,
                broadcast_stage=stage_entity.name,
            ),
        )

    dbg_game.player_session.add_agent_event(agent_event=agent_event)


#################################################################################################################################################
def notify_entities(
    dbg_game: DBGGame,
    entities: Set[Entity],
    agent_event: AnyAgentEvent,
) -> None:
    """向指定实体私发事件消息，并同步到玩家客户端。"""
    for entity in entities:
        add_human_message(
            dbg_game,
            entity,
            HumanMessage(
                content=agent_event.message,
                agent_event=agent_event.type,
            ),
        )
    dbg_game.player_session.add_agent_event(agent_event=agent_event)
