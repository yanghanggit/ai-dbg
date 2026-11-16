"""
DBG 游戏业务上下文。

`DBGGame` 保存一次游戏运行所需的世界状态、ECS context、玩家身份、领域事件出口、
实体名称索引与唯一 pipeline。用户会话历史由房间单独持有，不属于这里。
所有游戏领域操作都以模块函数的形式接收 `DBGGame`，不再把行为挂在这个对象上。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict

from ..entitas import Context, Entity
from ..models import WorldState
from .events import DomainEventSink, NullEventSink

if TYPE_CHECKING:
    from .pipelines.manager import RPGGameProcessPipeline


#################################################################################################################################################
@dataclass
class DBGGame:
    """DBG，Deck Building Game 的一次游戏运行上下文。"""

    name: str
    player_name: str
    player_actor: str
    world: WorldState
    ecs: Context = field(default_factory=Context)
    entity_index: Dict[str, Entity] = field(default_factory=dict)
    events: DomainEventSink = field(default_factory=NullEventSink)
    pipeline: RPGGameProcessPipeline = field(init=False)
    should_terminate: bool = False

    def __repr__(self) -> str:
        return f"<DBGGame name={self.name!r} player={self.player_name!r} entities={self.ecs.entity_count}>"
