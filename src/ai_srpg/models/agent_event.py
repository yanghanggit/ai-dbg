"""游戏事件定义模块"""

from typing import Annotated, Literal, Union, final

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


AnyAgentEvent = Annotated[
    Union[NoneEvent,],
    Field(discriminator="type"),
]
