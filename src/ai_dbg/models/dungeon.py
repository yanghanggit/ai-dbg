from datetime import datetime, timezone
from typing import Dict, List, final

from pydantic import BaseModel, Field

from .assets_meta import AssetKey
from .dungeon_room import AnyDungeonRoom


###############################################################################################################################################
@final
class Dungeon(BaseModel):
    """副本静态定义。

    仅用于加载 `.dungeons/*.json` 与副本列表；运行时进度、当前房间与战斗状态
    全部由 ECS 实体/组件持有，不再保存在这个模型里。
    """

    name: str
    rooms: List[AnyDungeonRoom]
    profile: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )  # 创建时间戳（UTC）
    assets: Dict[AssetKey, str] = Field(
        default_factory=dict
    )  # 副本封面等资源：AssetKey -> meta 路径（.assets/image/<file>.meta）
