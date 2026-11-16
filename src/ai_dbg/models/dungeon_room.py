from enum import StrEnum, unique
from typing import Annotated, Literal, Union, final

from pydantic import BaseModel, Field

from .entities import Stage


###############################################################################################################################################
@final
@unique
class DungeonRoomType(StrEnum):
    """副本房间类型；与静态定义中的 ``DungeonRoom.type`` 判别值一致。"""

    OPENING = "opening"
    COMBAT = "combat"


###############################################################################################################################################
class DungeonRoom(BaseModel):
    """副本房间基类（抽象关卡包装）：不直接实例化，具体房间见 OpeningRoom / CombatRoom。"""

    type: str  # 判别字段，子类收窄为各自的 Literal 值
    stage: Stage  # 必须，对应关卡场景


###############################################################################################################################################
@final
class CombatRoom(DungeonRoom):
    """战斗房间定义；运行时战斗状态由房间实体上的组件承载。"""

    type: Literal["combat"] = "combat"


###############################################################################################################################################
@final
class OpeningRoom(DungeonRoom):
    """开场房间（非战斗叙事场景，用于副本开场铺垫）"""

    type: Literal["opening"] = "opening"


###############################################################################################################################################
# 判别联合类型：基于 type 字段进行精确的反序列化。
# 只含具体房间：DungeonRoom 是抽象基类，"base" 房间不存在，故不进入联合。
AnyDungeonRoom = Annotated[
    Union[OpeningRoom, CombatRoom],
    Field(discriminator="type"),
]
