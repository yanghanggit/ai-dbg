"""记忆标记登记表。

标记是挂在记忆消息上的结构化额外属性（`HumanMessage`/`AIMessage` 的 `extra="allow"`），
用于事后审计：这些标记随消息落在 extra 中，据此区分
「谁写入的、属于哪一类」。extra 不校验拼写，写错只会静默失去可审计性，
因此这里集中登记词表，并由 `add_human_message` / `add_ai_message` 强制校验。

新增标记：先在此登记，再在调用处使用（未登记的标记会断言失败）。
"""

from typing import Final, FrozenSet

from pydantic import BaseModel

###############################################################################################################################################
# 词表：key = 标记名，value = 触发写入的系统/语义（仅作文档，不参与校验）
MEMORY_TAGS: Final[FrozenSet[str]] = frozenset(
    {
        # ---- 事件投递（广播 / 私发）----
        "agent_event",  # 事件类型（speak / trans_stage / none …）
        "broadcast_stage",  # 广播所属舞台；私发不带此标记
        # ---- agent loop ----
        "loop_id",  # agent_loop 起止标记
        "loop_id_end",
        # ---- 记忆自身维护 ----
        "keep_on_compact",  # 压缩时保留
        "replaced_messages",  # 被替换掉的整段消息
        "context_usage_ratio",  # 上下文占比（随最近一次 LLM 调用同步）
    }
)


###############################################################################################################################################
def assert_known_memory_tags(message: BaseModel) -> None:
    """校验消息上的结构化标记都在 `MEMORY_TAGS` 里，防止拼错后静默失去审计信息。"""
    unknown = set(message.model_extra or {}) - MEMORY_TAGS
    assert (
        not unknown
    ), f"{type(message).__name__} 使用了未登记的记忆标记 {sorted(unknown)}；请在 models/memory_tags.py 登记后再使用"


###############################################################################
__all__ = ["MEMORY_TAGS", "assert_known_memory_tags"]
