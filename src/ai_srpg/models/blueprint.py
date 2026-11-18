from typing import List, final

from pydantic import BaseModel

from .entities import Stage, World


###############################################################################################################################################################
# 生成世界的根文件，就是世界的起点
@final
class Blueprint(BaseModel):
    name: str
    player_actor: str
    campaign_setting: str
    system_rules: str  # 全局规则（角色扮演契约、副本定义、场景移动、战斗机制等）
    stages: List[Stage]
    # 世界级实体（全局、唯一、独立于场景）
    world_entities: List[World]


###############################################################################################################################################
