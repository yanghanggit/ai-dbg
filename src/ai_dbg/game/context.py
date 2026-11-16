"""
DBG 游戏业务上下文。

`DBGGame` 只保存一次游戏运行所需的数据：世界状态、ECS context、玩家会话、
实体名称索引与唯一 pipeline。所有游戏领域操作都以模块函数的形式接收
`DBGGame`，不再把行为挂在这个对象上。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict

from ..entitas import Context, Entity
from ..models import PlayerSession, WorldState

if TYPE_CHECKING:
    from .pipelines.manager import RPGGameProcessPipeline


#################################################################################################################################################
@dataclass
class DBGGame:
    """DBG，Deck Building Game 的业务上下文（纯数据对象）。"""

    name: str
    player_session: PlayerSession
    world: WorldState
    ecs: Context = field(default_factory=Context)
    entity_index: Dict[str, Entity] = field(default_factory=dict)
    pipeline: RPGGameProcessPipeline = field(init=False)
    should_terminate: bool = False

    def __repr__(self) -> str:
        return f"<DBGGame name={self.name!r} entities={self.ecs.entity_count}>"
