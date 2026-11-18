"""游戏实例组装入口：构造上下文并装配默认 pipeline。"""

from typing import Optional

from ..models import WorldState
from .context import SRPGGame
from .events import DomainEventSink
from .pipelines.build import build_game_pipeline


def create_srpg_game(
    *,
    name: str,
    player_name: str,
    player_actor: str,
    world: WorldState,
    events: Optional[DomainEventSink] = None,
) -> SRPGGame:
    """创建完整的游戏业务上下文（数据 + 唯一 pipeline）。

    ``player_name`` / ``player_actor`` 是构建玩家实体所需的领域身份；
    ``events`` 是应用层注入的领域事件出口，游戏本身不持有 PlayerSession。
    """
    srpg_game = SRPGGame(
        name=name,
        player_name=player_name,
        player_actor=player_actor,
        world=world,
    )
    if events is not None:
        srpg_game.events = events
    srpg_game.pipeline = build_game_pipeline(srpg_game)
    return srpg_game
