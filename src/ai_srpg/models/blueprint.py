from typing import List, final

from pydantic import BaseModel

from .entities import ActorBlueprint, StageBlueprint, WorldBlueprint


###############################################################################################################################################################
# 生成世界的根文件，就是世界的起点
@final
class Blueprint(BaseModel):
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
__all__ = ["Blueprint"]
