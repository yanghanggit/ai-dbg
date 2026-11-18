"""Agent LLM 记忆操作（基于 SRPGGame 的函数）。

包内按职责分层：``access`` 负责读写，``query`` 负责检索，
``compact`` 负责压缩；本模块只做统一导出，供调用方按需取用。
"""

from .access import (
    add_ai_message,
    add_human_message,
    add_system_message,
    get_agent_memory,
    insert_messages,
    remove_agent_memory,
    remove_message_range,
    remove_messages,
    replace_span,
    reset_agent_memory,
    sync_latest_context_usage_ratio,
)
from .compact import compact_agent_memory
from .constants import KEEP_ON_COMPACT_ATTR, REPLACED_MESSAGES_ATTR
from .query import MessagePredicate, filter_messages, find_marked_span

__all__ = [
    "MessagePredicate",
    "KEEP_ON_COMPACT_ATTR",
    "REPLACED_MESSAGES_ATTR",
    "add_ai_message",
    "add_human_message",
    "add_system_message",
    "compact_agent_memory",
    "filter_messages",
    "find_marked_span",
    "get_agent_memory",
    "insert_messages",
    "remove_agent_memory",
    "remove_message_range",
    "remove_messages",
    "replace_span",
    "reset_agent_memory",
    "sync_latest_context_usage_ratio",
]
