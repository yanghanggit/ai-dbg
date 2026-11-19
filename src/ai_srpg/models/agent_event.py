"""游戏领域事件：发生了什么。

事件是「发生了一件事」的最小描述，同时也是它在别人记忆里的那句话（``message``）。
结构化字段供审计、回放与会话历史使用，``message`` 供 agent 记忆使用——两者出自同一
个对象，所以记忆里说的话与事件里记的字段不会走散。

动作与事件一一对应：一个行为动作在同一次 pass 里产生一个事件。位置变化会被三处听见，
但事件只发布一次：投递范围是「谁听见」，事件是「谁做了什么」。
"""

from typing import Annotated, Literal, Tuple, Union, final

from pydantic import BaseModel, ConfigDict, Field


class AgentEvent(BaseModel):
    """事件基类（抽象）：只声明公共字段，不直接实例化；具体事件继承它并把 type 收窄为 Literal。"""

    model_config = ConfigDict(extra="forbid")

    type: str
    message: str


@final
class NoneEvent(AgentEvent):
    """未分类事件：兜底形态（type = "none"）"""

    type: Literal["none"] = "none"


@final
class StagePulse(AgentEvent):
    """舞台脉动：此刻某个局部舞台里有哪些角色。"""

    type: Literal["stage_pulse"] = "stage_pulse"
    stage: str
    actors: Tuple[str, ...]


@final
class ActorSpoke(AgentEvent):
    """角色在所在区域里说了一句话。"""

    type: Literal["actor_spoke"] = "actor_spoke"
    actor: str
    stage: str
    content: str


@final
class ActorWaited(AgentEvent):
    """角色这一轮没有动。``stage`` 是它当时所在的舞台：地图上也算一处位置。"""

    type: Literal["actor_waited"] = "actor_waited"
    actor: str
    stage: str


@final
class ActorTraveled(AgentEvent):
    """角色在战场上走到某一格。"""

    type: Literal["actor_traveled"] = "actor_traveled"
    actor: str
    stage: str
    x: int
    y: int


@final
class ActorEnteredStage(AgentEvent):
    """角色走进脚下的据点，落到据点根。"""

    type: Literal["actor_entered_stage"] = "actor_entered_stage"
    actor: str
    stage: str


@final
class ActorExitedStage(AgentEvent):
    """角色离开据点，回到据点所在的战场格子。"""

    type: Literal["actor_exited_stage"] = "actor_exited_stage"
    actor: str
    stage: str


@final
class ActorMovedWithinStage(AgentEvent):
    """角色在据点内部从一处区域走到另一处。"""

    type: Literal["actor_moved_within_stage"] = "actor_moved_within_stage"
    actor: str
    stage: str
    destination: str


AnyAgentEvent = Annotated[
    Union[
        NoneEvent,
        StagePulse,
        ActorSpoke,
        ActorWaited,
        ActorTraveled,
        ActorEnteredStage,
        ActorExitedStage,
        ActorMovedWithinStage,
    ],
    Field(discriminator="type"),
]

###############################################################################
__all__ = [
    "ActorEnteredStage",
    "ActorExitedStage",
    "ActorMovedWithinStage",
    "ActorSpoke",
    "ActorTraveled",
    "ActorWaited",
    "AgentEvent",
    "AnyAgentEvent",
    "NoneEvent",
    "StagePulse",
]
