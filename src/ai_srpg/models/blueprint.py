"""蓝图：构建期输入，描述一局游戏要落进 ECS 的东西。

一个实体只承载三样东西：名字、进游戏后的第一条记忆（``system_message``）、组件数据。
三个声明类把类别写在类型上——装配期据此要求实体带对了标记组件，运行期的行为差异
全部由组件承担，因此这里没有类别枚举。
"""

from typing import Dict, List, final

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


###############################################################################################################################################################
@final
class Blueprint(BaseModel):
    """一局的构建输入：世界、舞台与角色，加上组装提示词用的故事级设定。"""

    name: str
    campaign_setting: str  # 组装 system_message 用，不进 ECS
    global_rules: (
        str  # 所有实体共同遵守的纯机制规则（扮演契约、实体类型与全名、舞台移动等）
    )
    # 舞台与角色的关系由 ActorComponent.current_stage 表达，两级列表不再互相嵌套
    stages: List[StageBlueprint]
    actors: List[ActorBlueprint]
    # 世界级实体（全局、唯一、独立于舞台）
    world_entities: List[WorldBlueprint]


###############################################################################
__all__ = ["ActorBlueprint", "Blueprint", "StageBlueprint", "WorldBlueprint"]
