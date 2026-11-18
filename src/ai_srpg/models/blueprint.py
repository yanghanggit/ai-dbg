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
    global_rules: (
        str  # 所有实体共同遵守的纯机制规则（扮演契约、实体类型与全名、舞台移动等）
    )
    stages: List[Stage]
    # 世界级实体（全局、唯一、独立于舞台）
    world_entities: List[World]


###############################################################################################################################################
