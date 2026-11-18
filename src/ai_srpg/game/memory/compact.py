"""agent 记忆压缩：把首条 system prompt 之外的内容折叠成一条摘要。"""

from ...entitas import Entity
from ...models import HumanMessage
from ..context import SRPGGame
from .access import get_agent_memory, reset_agent_memory
from .constants import KEEP_ON_COMPACT_ATTR


#################################################################################################################################################
def compact_agent_memory(
    srpg_game: SRPGGame, entity: Entity, human_message: HumanMessage
) -> None:
    """将 agent 记忆中除首条 system 消息外的全部消息压缩为一条摘要。"""
    messages = get_agent_memory(srpg_game, entity).messages
    preserved = [m for m in messages[1:] if getattr(m, KEEP_ON_COMPACT_ATTR, False)]
    reset_agent_memory(srpg_game, entity, [human_message, *preserved])
