"""ECS 组件定义。添加到实体后由对应系统读取处理。

实体名在 ``Entity.name`` 与快照的键里，组件不再重复保存它；标记组件只带
真正的状态（例如角色所在的舞台）。
"""

from typing import Optional, final

from pydantic import model_validator

from ..entitas.components import Component
from .registry import register_component_type


############################################################################################################
@final
@register_component_type
class IdentityComponent(Component):
    """为实体提供创建顺序与全局唯一 ID（名字由实体自身持有）。"""

    creation_order: int  # 序列化时保证顺序一致性
    entity_id: str  # UUID 格式


############################################################################################################
@final
@register_component_type
class WorldComponent(Component):
    """标记实体为世界级实体（全局、唯一、独立于舞台）。"""


############################################################################################################
@final
@register_component_type
class StageComponent(Component):
    """标记实体为舞台（角色可停留的地点），记录挂在哪个舞台之下。"""

    parent_stage: Optional[str] = None  # 树上层的舞台；根为 None


############################################################################################################
@final
@register_component_type
class GlobalStageComponent(Component):
    """标记实体为全局舞台：舞台树的根，自带一片网格坐标系。"""

    width: int
    height: int


############################################################################################################
@final
@register_component_type
class PositionComponent(Component):
    """在所属舞台网格上的格子坐标（左上角为原点）。"""

    x: int
    y: int


############################################################################################################
@final
@register_component_type
class ActorComponent(Component):
    """标记实体为角色类型，记录当前所在舞台。"""

    current_stage: str  # 当前所在舞台名称


############################################################################################################
@final
@register_component_type
class EnvironmentComponent(Component):
    """舞台环境：``base_environment`` 是内容侧写定的底稿，``narrative`` 是当前叙述。

    未给出 ``narrative`` 时与 ``base_environment`` 相同（与外观的派生同一套路）。
    叙述只写舞台自身的物理状态——光、声、气味、地形，不写谁来过、留下了什么；
    在场者属于角色自己的状态，不该从环境里推断出来。
    """

    base_environment: str  # 内容侧写定的环境底稿
    narrative: str = ""  # 当前环境叙述，之后由系统按状态更新

    @model_validator(mode="after")
    def _fill_narrative(self) -> "EnvironmentComponent":
        if not self.narrative:
            object.__setattr__(self, "narrative", self.base_environment)
        return self


############################################################################################################
@final
@register_component_type
class NPCComponent(Component):
    """标记角色是 NPC：先只做类型记录，行为差异等真正需要时再补。"""


############################################################################################################
@final
@register_component_type
class PlayerComponent(Component):
    """标记角色由某玩家控制；一个玩家控制一个角色。"""

    user_name: str


############################################################################################################
@final
@register_component_type
class DestroyComponent(Component):
    """标记实体在下一帧销毁。"""


############################################################################################################
@final
@register_component_type
class AppearanceComponent(Component):
    """存储角色外观描述；未给出 ``appearance`` 时与 ``base_body`` 相同。"""

    base_body: str  # 基础身体形态描述（不含装备）
    appearance: str = ""  # 最终外观描述（含装备）

    @model_validator(mode="after")
    def _fill_appearance(self) -> "AppearanceComponent":
        if not self.appearance:
            object.__setattr__(self, "appearance", self.base_body)
        return self


###############################################################################
__all__ = [
    "ActorComponent",
    "AppearanceComponent",
    "DestroyComponent",
    "EnvironmentComponent",
    "GlobalStageComponent",
    "IdentityComponent",
    "NPCComponent",
    "PlayerComponent",
    "PositionComponent",
    "StageComponent",
    "WorldComponent",
]
