"""ECS 组件定义。添加到实体后由对应系统读取处理。"""

from typing import final

from ..entitas.components import Component
from .registry import register_component_type


############################################################################################################
@final
@register_component_type
class IdentityComponent(Component):
    """为实体提供可读名称、创建顺序与全局唯一 ID。"""

    name: str
    creation_order: int  # 序列化时保证顺序一致性
    entity_id: str  # UUID 格式


############################################################################################################
@final
@register_component_type
class WorldComponent(Component):
    """标记实体为世界级实体（全局、唯一、独立于舞台）。"""

    name: str


############################################################################################################
@final
@register_component_type
class StageComponent(Component):
    """标记实体为舞台类型。"""

    name: str


############################################################################################################
@final
@register_component_type
class ActorComponent(Component):
    """标记实体为角色类型，记录当前所在舞台。"""

    name: str
    current_stage: str  # 当前所在舞台名称


############################################################################################################
@final
@register_component_type
class EnvironmentComponent(Component):
    """舞台环境叙述，由 AI 根据当前状态动态生成，为后续行动规划提供背景信息。"""

    name: str
    narrative: str  # 叙述性描述文本


############################################################################################################
@final
@register_component_type
class PlayerComponent(Component):
    """标记角色由玩家控制（全局唯一）。"""

    player_name: str


############################################################################################################
@final
@register_component_type
class DestroyComponent(Component):
    """标记实体在下一帧销毁。"""

    name: str


############################################################################################################
@final
@register_component_type
class AppearanceComponent(Component):
    """存储角色外观描述；当前无时装系统，`appearance` 初始等于 `base_body`。"""

    name: str
    base_body: str  # 基础身体形态描述（不含装备）
    appearance: str  # 最终外观描述（含装备）


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
