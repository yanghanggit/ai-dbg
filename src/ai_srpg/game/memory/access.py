"""agent 记忆的读写入口：消息追加、替换、删除与上下文占比同步。"""

from typing import Any, Dict, List, Optional, Sequence

from loguru import logger

from ...entitas import Entity
from ...models import (
    AgentMemory,
    AIMessage,
    ChatMessage,
    HumanMessage,
    SystemMessage,
    assert_known_memory_tags,
    find_message,
)
from ..context import SRPGGame


#################################################################################################################################################
def _dump_messages(
    messages: Sequence[ChatMessage], dump_attr: str
) -> List[Dict[str, Any]]:
    """把一段消息 dump 成 JSON 原生 dict 列表。"""
    dumped: List[Dict[str, Any]] = []
    for msg in messages:
        data = msg.model_dump(mode="json")
        data.pop(dump_attr, None)
        dumped.append(data)
    return dumped


#################################################################################################################################################
def get_agent_memory(srpg_game: SRPGGame, entity: Entity) -> AgentMemory:
    """获取或创建实体的 LLM 记忆。"""
    return srpg_game.agent_memory_store.get_or_create(entity.name)


#################################################################################################################################################
def remove_agent_memory(srpg_game: SRPGGame, entity: Entity) -> None:
    """从 agent 记忆容器中移除实体的 LLM 记忆。"""
    if entity.name in srpg_game.agent_memory_store:
        logger.debug(
            f"remove_agent_memory: {entity.name} in agent_memory_store, remove it"
        )
        srpg_game.agent_memory_store.remove(entity.name)


#################################################################################################################################################
def add_system_message(
    srpg_game: SRPGGame, entity: Entity, system_message: SystemMessage
) -> None:
    """添加系统消息到实体的 LLM 记忆，必须是第一条消息。"""
    agent_memory = get_agent_memory(srpg_game, entity)
    assert len(agent_memory.messages) == 0, "system message should be the first message"
    agent_memory.messages.append(system_message)


#################################################################################################################################################
def add_human_message(
    srpg_game: SRPGGame, entity: Entity, human_message: HumanMessage
) -> None:
    """添加用户消息到实体的 LLM 记忆（校验结构化标记已登记）。"""
    assert_known_memory_tags(human_message)
    get_agent_memory(srpg_game, entity).messages.append(human_message)


#################################################################################################################################################
def add_ai_message(srpg_game: SRPGGame, entity: Entity, ai_message: AIMessage) -> None:
    """添加 AI 响应消息到实体的 LLM 记忆。"""
    assert_known_memory_tags(ai_message)
    if ai_message.content == "":
        logger.warning(
            f"add_ai_message: {entity.name} 的 AI 消息正文为空（tool_calls={bool(ai_message.additional_kwargs.get('tool_calls'))}），仍写入记忆"
        )
    agent_memory = get_agent_memory(srpg_game, entity)
    _sync_context_usage_ratio(agent_memory, ai_message)
    agent_memory.messages.append(ai_message)


#################################################################################################################################################
def _sync_context_usage_ratio(agent_memory: AgentMemory, ai_message: AIMessage) -> None:
    context_usage_ratio = getattr(ai_message, "context_usage_ratio", None)
    if context_usage_ratio is not None:
        agent_memory.context_usage_ratio = context_usage_ratio


#################################################################################################################################################
def sync_latest_context_usage_ratio(srpg_game: SRPGGame, entity: Entity) -> None:
    """从记忆中最新的 AI 消息同步上下文占比到 AgentMemory。"""
    agent_memory = get_agent_memory(srpg_game, entity)
    ai_message = find_message(
        agent_memory.messages, lambda m: isinstance(m, AIMessage), reverse=True
    )
    if isinstance(ai_message, AIMessage):
        _sync_context_usage_ratio(agent_memory, ai_message)


#################################################################################################################################################
def reset_agent_memory(
    srpg_game: SRPGGame,
    entity: Entity,
    new_messages: Sequence[ChatMessage] = (),
) -> None:
    """把实体记忆重制为「首条 system prompt + new_messages」。"""
    agent_memory = get_agent_memory(srpg_game, entity)
    assert len(agent_memory.messages) > 0 and isinstance(
        agent_memory.messages[0], SystemMessage
    ), f"reset_agent_memory 要求实体 {entity.name!r} 首条消息必须是 SystemMessage"

    removed_count = len(agent_memory.messages) - 1
    agent_memory.messages[1:] = list(new_messages)
    agent_memory.context_usage_ratio = 0.0
    logger.info(
        f"[reset_agent_memory] ⚠️ 危险操作：已重制 {entity.name!r} 的 agent memory，丢弃 {removed_count} 条旧消息，写入 {len(new_messages)} 条新消息（保留首条 system prompt）"
    )


#######################################################################################################################################
def remove_messages(
    srpg_game: SRPGGame, entity: Entity, messages: Sequence[ChatMessage]
) -> int:
    """从实体记忆中删除指定的消息对象。"""
    if len(messages) == 0:
        return 0
    history = get_agent_memory(srpg_game, entity).messages
    original_length = len(history)
    history[:] = [msg for msg in history if msg not in messages]
    deleted_count = original_length - len(history)
    if deleted_count > 0:
        logger.debug(
            f"Deleted {deleted_count} message(s) from {entity.name}'s chat history."
        )
    return deleted_count


#######################################################################################################################################
def remove_message_range(
    srpg_game: SRPGGame,
    entity: Entity,
    begin_message: ChatMessage,
    end_message: ChatMessage,
) -> List[ChatMessage]:
    """从实体记忆中删除指定范围的消息（包含两端）。"""
    assert (
        begin_message != end_message
    ), "begin_message and end_message should not be the same"
    agent_memory = get_agent_memory(srpg_game, entity)
    begin_message_index = agent_memory.messages.index(begin_message)
    end_message_index = agent_memory.messages.index(end_message) + 1
    deleted_messages = agent_memory.messages[begin_message_index:end_message_index]
    del agent_memory.messages[begin_message_index:end_message_index]
    logger.debug(f"remove_message_range= {entity.name}")
    logger.debug(f"begin_message: \n{begin_message.model_dump_json(indent=2)}")
    logger.debug(f"end_message: \n{end_message.model_dump_json(indent=2)}")
    return deleted_messages


#######################################################################################################################################
def replace_span(
    srpg_game: SRPGGame,
    entity: Entity,
    start_index: int,
    end_index: int,
    new_messages: Sequence[ChatMessage],
    *,
    dump_attr: Optional[str] = None,
) -> List[ChatMessage]:
    """用 new_messages 替换记忆中 ``[start_index, end_index)`` 半开区间。"""
    agent_memory = get_agent_memory(srpg_game, entity)
    replaced = agent_memory.messages[start_index:end_index]
    new_list = list(new_messages)
    agent_memory.messages[start_index:end_index] = new_list
    attach_dump = dump_attr is not None and len(new_list) > 0
    if dump_attr is not None and len(new_list) > 0:
        setattr(new_list[-1], dump_attr, _dump_messages(replaced, dump_attr))
    logger.debug(
        f"replace_span: {entity.name} 用 {len(new_list)} 条替换 [{start_index}:{end_index}) 的 {len(replaced)} 条消息"
        + (f"（dump→{dump_attr}）" if attach_dump else "")
    )
    return replaced


#######################################################################################################################################
def insert_messages(
    srpg_game: SRPGGame,
    entity: Entity,
    index: int,
    messages: Sequence[ChatMessage],
) -> None:
    """在实体记忆的指定位置插入一段连续的消息序列。"""
    if len(messages) == 0:
        return
    agent_memory = get_agent_memory(srpg_game, entity)
    agent_memory.messages[index:index] = messages
    # 批量插入同样要延续「最近一次调用的上下文占比」信号，否则占比停在 0，
    # 依赖它做判断的地方（例如自动压缩阈值）永远看不到真实的满度
    sync_latest_context_usage_ratio(srpg_game, entity)
    logger.debug(
        f"insert_messages: inserted {len(messages)} message(s) at index {index} for {entity.name}"
    )
