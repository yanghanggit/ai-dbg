"""游戏事件定义模块"""

from typing import Annotated, Literal, Union, final

from pydantic import BaseModel, ConfigDict, Field


####################################################################################################################################
class AgentEvent(BaseModel):
    """事件基类（抽象）：只声明公共字段，不直接实例化；具体事件继承它并把 type 收窄为 Literal。"""

    # 禁止额外字段：具体事件的 payload 不会被静默丢弃；未分类事件请显式用 NoneEvent
    model_config = ConfigDict(extra="forbid")

    type: str
    message: str


####################################################################################################################################
# 未分类事件（兜底）
@final
class NoneEvent(AgentEvent):
    """未分类事件：兜底形态（type = "none"）"""

    type: Literal["none"] = "none"


####################################################################################################################################
@final
class TransStageEvent(AgentEvent):
    """场景转换事件"""

    type: Literal["trans_stage"] = "trans_stage"
    actor: str
    stage: str
    target: str


####################################################################################################################################
@final
class CombatArbitrationEvent(AgentEvent):
    """战斗裁决事件"""

    type: Literal["combat_arbitration"] = "combat_arbitration"
    stage: str
    combat_log: str
    narrative: str


####################################################################################################################################
####################################################################################################################################
# 具体事件的判别联合类型：基于 type 字段（Literal 值）进行精确的反序列化。
# 每个成员（含兜底的 NoneEvent）都以 Literal 作为判别键，因此是标准 discriminated union；
# 未知 type 会明确报 ValidationError，不再靠 smart-union 兜。
_ConcreteAgentEvent = Annotated[
    Union[
        TransStageEvent,
        CombatArbitrationEvent,
        NoneEvent,
    ],
    Field(discriminator="type"),
]

AnyAgentEvent = _ConcreteAgentEvent
####################################################################################################################################
