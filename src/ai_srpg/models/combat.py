"""战斗相关模型定义。

战斗、回合与回合行动槽都已迁移到 ECS：它们都是实体，运行时状态由实体上的
组件持有。本模块只保留枚举、值对象与只读视图，供系统、API 与测试消费。
"""

from enum import IntEnum, StrEnum, unique
from typing import List, Optional, final

from pydantic import BaseModel, Field, computed_field


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
class CombatTurnStatus(StrEnum):
    """回合行动槽的生命周期状态。"""

    PENDING = "pending"  # 尚未行动
    COMPLETED = "completed"  # 已过牌 / 已交出行动权
    DEAD = "dead"  # 行动者已死亡，跳过该槽


###############################################################################################################################################
@final
class CombatTurnView(BaseModel):
    """回合行动槽的只读投影；运行时数据由行动槽实体持有。"""

    name: str
    combat_name: str
    round_name: str
    actor_name: str
    order_index: int
    status: CombatTurnStatus = CombatTurnStatus.PENDING
    energy: int = 2
    is_current: bool = False


###############################################################################################################################################
@final
class CombatRoundView(BaseModel):
    """回合的只读投影；运行时数据由回合与行动槽实体持有。"""

    index: int
    is_completed: bool = False
    draw_completed: bool = False
    turns: List[CombatTurnView] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def action_order(self) -> List[str]:
        """按行动槽顺序返回角色名。"""
        return [turn.actor_name for turn in self.turns]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def completed_actors(self) -> List[str]:
        """按行动槽顺序返回已交出行动权的角色名。"""
        return [
            turn.actor_name
            for turn in self.turns
            if turn.status == CombatTurnStatus.COMPLETED
        ]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def current_actor(self) -> Optional[str]:
        """返回当前行动槽对应的角色名；没有当前行动槽时返回 None。"""
        for turn in self.turns:
            if turn.is_current and turn.status == CombatTurnStatus.PENDING:
                return turn.actor_name
        return None


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
