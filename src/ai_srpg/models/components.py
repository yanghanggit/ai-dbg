"""ECS 组件定义。添加到实体后由对应系统读取处理。

实体名在 ``Entity.name`` 与快照的键里，组件不再重复保存它；标记组件只带
真正的状态（例如角色所在的舞台）。
"""

from typing import final

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
    """标记实体为舞台类型。"""


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
    """舞台环境叙述，由 AI 根据当前状态动态生成，为后续行动规划提供背景信息。"""

    narrative: str  # 叙述性描述文本


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
    "IdentityComponent",
    "PlayerComponent",
    "StageComponent",
    "WorldComponent",
]
