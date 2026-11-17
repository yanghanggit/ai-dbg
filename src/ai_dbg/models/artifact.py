"""神器（Artifact）模型定义。

神器与 `Card` 同级：独立的战斗价值模型，不进道具流（不属于 `Item`/`AnyItem`），
由 Actor/Stage 通过 `ReliquaryComponent` 携带。当前只保留数据形状，不进入战斗结算。
"""

from typing import final
from uuid import uuid4

from pydantic import BaseModel, Field

from .str_list import NormalizedStrList


###############################################################################################################################################
@final
class Artifact(BaseModel):
    """神器：场景级战斗修正规则的数据载体；当前不进入战斗结算。"""

    name: str
    description: str  # 叙事锚点：神器的意象与来历，不含数值
    source: str = ""  # 来源/注入者名称；空字符串表示来源未知
    modifiers: NormalizedStrList = []  # 修正规则（多值，预留数据）：当前战斗结算不消费
    uuid: str = Field(default_factory=lambda: str(uuid4()))  # 全局唯一标识符
