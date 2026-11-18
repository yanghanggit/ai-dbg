"""游戏实例组装入口：构造上下文并装配默认 pipeline。"""

from typing import Optional

from ..models import WorldState
from .context import SRPGGame
from .events.sink import DomainEventSink
from .pipelines.build import build_game_pipeline


def create_srpg_game(
    *,
    name: str,
    world: WorldState,
    events: Optional[DomainEventSink] = None,
) -> SRPGGame:
    """创建完整的游戏业务上下文（数据 + 唯一 pipeline）。

    ``events`` 是应用层注入的领域事件出口，游戏本身不持有 PlayerSession。
    玩家身份只在构建世界时由 ``build_from_blueprint`` 一次性写入 ECS。
    """
    srpg_game = SRPGGame(
        name=name,
        world=world,
        events=events,
    )
    srpg_game.pipeline = build_game_pipeline(srpg_game)
    return srpg_game
