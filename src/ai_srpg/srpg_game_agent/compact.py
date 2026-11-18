"""上下文压缩动作：加载快照、压缩目标实体记忆，并保存结果快照。"""

from dataclasses import dataclass
from typing import Optional

from ..game.memory import compact_agent_memory, get_agent_memory
from ..models import HumanMessage, SystemMessage
from ..services.offline_game import load_or_create_game, save_game_snapshot

DEFAULT_COMPACT_SUMMARY = "（上下文已手动压缩，此前的对话在此折叠。）"


@dataclass(frozen=True)
class CompactContextOutcome:
    entity_name: str
    before_messages: int
    after_messages: int
    before_ratio: float
    after_ratio: float
    snapshot_id: int


###############################################################################
async def compact_context_game(
    user: str,
    game: str,
    target: str,
    snapshot_id: Optional[int],
    *,
    summary: str = DEFAULT_COMPACT_SUMMARY,
) -> CompactContextOutcome:
    """手动压缩指定实体的 LLM 记忆，并保存新快照。"""
    srpg_game = await load_or_create_game(user, game, snapshot_id=snapshot_id)
    entity = srpg_game.get_entity_by_name(target)
    if entity is None:
        raise LookupError(f"找不到实体: {target!r}")

    memory = get_agent_memory(srpg_game, entity)
    if not memory.messages:
        raise ValueError(f"实体 {target!r} 没有 agent 记忆可压缩")
    if not isinstance(memory.messages[0], SystemMessage):
        raise ValueError(f"实体 {target!r} 的首条记忆不是 SystemMessage")

    before_messages = len(memory.messages)
    before_ratio = memory.context_usage_ratio

    compact_agent_memory(srpg_game, entity, HumanMessage(content=summary))

    after_messages = len(memory.messages)
    after_ratio = memory.context_usage_ratio
    new_snapshot_id = save_game_snapshot(user, srpg_game)
    return CompactContextOutcome(
        entity_name=target,
        before_messages=before_messages,
        after_messages=after_messages,
        before_ratio=before_ratio,
        after_ratio=after_ratio,
        snapshot_id=new_snapshot_id,
    )


__all__ = ["CompactContextOutcome", "compact_context_game"]
