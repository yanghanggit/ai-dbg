"""战斗相关模型定义。

`Combat` / `Round` 的运行时状态已经迁移到 ECS：战斗是实体，回合也是实体。
本模块只保留枚举、值对象与只读视图，供系统、API 与测试消费。
"""

from enum import IntEnum, StrEnum, unique
from typing import List, Optional, final

from pydantic import BaseModel, Field


###############################################################################################################################################
# 战斗状态枚举
@final
@unique
class CombatState(IntEnum):
    NONE = 0  # 无状态
    INITIALIZATION = 1  # 初始化，需要同步一些数据与状态
    ONGOING = 2  # 运行中，不断进行战斗推理
    COMPLETE = 3  # 结束，需要进行结算
    POST_COMBAT = 4  # 战斗等待进入新一轮战斗或者回家


###############################################################################################################################################
# 表示战斗的状态
@final
@unique
class CombatResult(IntEnum):
    NONE = 0  # 无结果
    WIN = 1  # 胜利
    LOSE = 2  # 失败


###############################################################################################################################################
@final
@unique
class RoundEntryKind(StrEnum):
    """回合内一条记录的种类标记。"""

    CARDS = "cards"  # 出牌 / 回合结束仲裁
    CONSUMABLE = "consumable"  # 使用消耗品
    GEAR = "gear"  # 装备转化
    ARTIFACT = "artifact"  # 场景神器仲裁
    AUTONOMOUS = "autonomous"  # 卡牌自主运行仲裁（pass turn，在回合结束之后）
    FAILED = "failed"  # 仲裁未完成（未提交 / 循环异常）：无 HP 变更，仅留痕迹


###############################################################################################################################################
@final
class RoundEntry(BaseModel):
    """回合内的一条操作记录。

    把原先分散的 log / narrative 合并为同一条目，使跨种类的操作先后顺序可被表达。
    """

    kind: RoundEntryKind  # 种类标记
    log: str  # 战斗数据日志
    narrative: str  # 叙事文本


###############################################################################################################################################
@final
class CombatRoundView(BaseModel):
    """回合的只读投影；运行时数据由回合实体上的组件持有。"""

    index: int
    completed_actors: List[str] = Field(default_factory=list)
    action_order: List[str] = Field(default_factory=list)
    current_actor: Optional[str] = None
    is_completed: bool = False
    draw_completed: bool = False
    entries: List[RoundEntry] = Field(default_factory=list)


###############################################################################################################################################
@final
class CombatView(BaseModel):
    """战斗的只读投影；运行时数据由战斗/回合实体上的组件持有。"""

    name: str
    state: CombatState = CombatState.NONE
    result: CombatResult = CombatResult.NONE
    rounds: List[CombatRoundView] = Field(default_factory=list)
    retreated: bool = False

    ########################################################################################################################
    @property
    def is_ongoing(self) -> bool:
        return self.state == CombatState.ONGOING

    ########################################################################################################################
    @property
    def is_combat_completed(self) -> bool:
        return self.state == CombatState.COMPLETE

    ########################################################################################################################
    @property
    def is_initializing(self) -> bool:
        return self.state == CombatState.INITIALIZATION

    ########################################################################################################################
    @property
    def is_post_combat(self) -> bool:
        return self.state == CombatState.POST_COMBAT

    ########################################################################################################################
    @property
    def is_won(self) -> bool:
        return self.result == CombatResult.WIN

    ########################################################################################################################
    @property
    def is_lost(self) -> bool:
        return self.result == CombatResult.LOSE

    ########################################################################################################################
    @property
    def latest_round(self) -> Optional[CombatRoundView]:
        if len(self.rounds) == 0:
            return None
        return self.rounds[-1]
