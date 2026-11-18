from enum import StrEnum, unique
from typing import Dict, List, final

from pydantic import BaseModel, Field

from ..entitas import EntityData


###############################################################################################################################################
@final
@unique
class ActorType(StrEnum):
    """角色类别。当前仅 ``NONE``（未分类）；具体类别随玩法扩展再补。"""

    NONE = "None"


###############################################################################################################################################
@final
@unique
class StageType(StrEnum):
    """场景类别。当前仅 ``NONE``（未分类）；具体类别随玩法扩展再补。"""

    NONE = "None"


###############################################################################################################################################
@final
class Actor(BaseModel):
    name: str
    type: ActorType
    profile: str
    base_body: str
    system_message: str
    components: EntityData = {}
    assets: Dict[str, str] = Field(
        default_factory=dict
    )  # 资源键（业务层约定）-> meta 路径（.assets/image/<file>.meta）


###############################################################################################################################################
@final
class Stage(BaseModel):
    name: str
    type: StageType
    profile: str
    system_message: str
    actors: List[Actor]
    components: EntityData = {}
    assets: Dict[str, str] = Field(
        default_factory=dict
    )  # 资源键（业务层约定）-> meta 路径（.assets/image/<file>.meta）


###############################################################################################################################################
@final
class World(BaseModel):
    name: str
    system_message: str
    components: EntityData = {}


###############################################################################################################################################
