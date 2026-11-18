"""agent 记忆的检索操作：按谓词过滤、按结构化标记定位消息段。"""

from typing import Any, Callable, List, Optional, Sequence

from loguru import logger

from ...entitas import Entity
from ...models import (
    ChatMessage,
    MessageSpan,
)
from ...models import (
    find_marked_span as find_marked_span_in_messages,
)
from ..context import SRPGGame
from .access import get_agent_memory

MessagePredicate = Callable[[ChatMessage, int, Sequence[ChatMessage]], bool]


#################################################################################################################################################
def find_marked_span(
    srpg_game: SRPGGame,
    entity: Entity,
    start_attr: str,
    value: Any,
    *,
    end_attr: Optional[str] = None,
) -> Optional[MessageSpan[ChatMessage]]:
    """按标记属性在实体记忆中定位一段连续消息。"""
    return find_marked_span_in_messages(
        get_agent_memory(srpg_game, entity).messages,
        start_attr,
        value,
        end_attr=end_attr,
    )


#################################################################################################################################################
def filter_messages(
    srpg_game: SRPGGame,
    entity: Entity,
    predicate: MessagePredicate,
    reverse_order: bool = True,
) -> List[ChatMessage]:
    """根据外部传入的谓词函数过滤实体记忆中的消息。"""
    messages = get_agent_memory(srpg_game, entity).messages
    found_messages: List[ChatMessage] = []
    indices = (
        range(len(messages) - 1, -1, -1) if reverse_order else range(len(messages))
    )
    for index in indices:
        chat_message = messages[index]
        try:
            if predicate(chat_message, index, messages):
                found_messages.append(chat_message)
        except Exception as e:
            logger.error(f"filter_messages error for {entity.name}: {e}")
            continue
    return found_messages
