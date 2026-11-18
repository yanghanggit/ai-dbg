"""记忆标记登记表。

标记是挂在记忆消息上的结构化额外属性（`HumanMessage`/`AIMessage` 的 `extra="allow"`），
用于事后审计：这些标记随消息落在 `extra=[...]` 中，据此区分
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
        "agent_event",  # 事件类型（speak / trans_stage / combat_arbitration / none …）
        "broadcast_stage",  # 广播所属场景；私发不带此标记
        # ---- 战斗 ----
        "combat_decision",  # 战斗决策记录：做了什么 + 原因（出牌事实折在正文里）
        "draw_cards_round_number",  # 怪物出牌决策请求：抽牌时刻的回合号
        "combat_initialization",  # 战斗初始化（演员侧与场景侧同一事件同一标记）
        "combat_outcome",  # 战斗胜负通知（值 = 场景名，按各阵营视角生成文本）
        "received_card",  # 传递副本落地的卡牌摘要（接收方）
        "transfer_outcome",  # 传递结果摘要：牌名 + 每个接收方份数（给出方）
        "unplayable_card",  # 不可出牌的卡被拦截
        "death_notification",  # HP 归零通知
        "stats_update",  # HP / 属性变化通知
        # ---- 副本与场景 ----
        "dungeon_lifecycle_entry",  # 进入副本
        "dungeon_lifecycle_stage_advance",  # 推进关卡
        "dungeon_lifecycle_completion",  # 完成副本并离场
        "dungeon_lifecycle_retreat",  # 战斗撤退
        "opening_initialization",  # 副本开场场景感知
        "environment_initialization",  # 场景环境描述生成
        # ---- 物品与状态 ----
        "card_pile_change",  # 牌堆变更说明（值 = {change, deltas}，只写给容器主人）
        # ---- 记忆自身维护 ----
        "loop_id",  # agent_loop 起止标记
        "loop_id_end",
        "keep_on_compact",  # 压缩时保留
        "replaced_messages",  # 被替换掉的整段消息
        "removed_messages_content",  # 压缩前的原始历史
        "context_compaction",  # 阈值压缩生成的摘要消息
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
