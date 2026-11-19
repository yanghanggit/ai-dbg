"""蓝图实体：构建期输入，一个实体名下要落进 ECS 的东西。

三个类只负责把类别写在类型上——装配期据此要求实体带对了标记组件，运行期的行为
差异全部由组件承担，因此这里没有类别枚举。``system_message`` 是实体进游戏后的
``memories[0]``；除此之外的一切状态都必须写成 ``components`` 里的组件数据。
"""

from typing import Dict, final

from pydantic import BaseModel, Field

from ..entitas import EntityData


###############################################################################################################################################
@final
class ActorBlueprint(BaseModel):
    """角色声明；所在舞台写在 ``ActorComponent.current_stage`` 里。"""

    name: str
    system_message: str
    components: EntityData = {}
    assets: Dict[str, str] = Field(
        default_factory=dict
    )  # 资源键（业务层约定）-> meta 路径（.assets/image/<file>.meta）


###############################################################################################################################################
@final
class StageBlueprint(BaseModel):
    """舞台声明；舞台上有什么由各角色的 ``current_stage`` 决定。"""

    name: str
    system_message: str
    components: EntityData = {}
    assets: Dict[str, str] = Field(
        default_factory=dict
    )  # 资源键（业务层约定）-> meta 路径（.assets/image/<file>.meta）


###############################################################################################################################################
@final
class WorldBlueprint(BaseModel):
    """世界声明：高于舞台但不出场，只给因果、不给行动。"""

    name: str
    system_message: str
    components: EntityData = {}


###############################################################################
__all__ = ["ActorBlueprint", "StageBlueprint", "WorldBlueprint"]
