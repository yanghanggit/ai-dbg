"""游戏实例组装入口：构造上下文并装配默认 pipeline。"""

from typing import Optional

from ..models import WorldState
from .context import DBGGame
from .events import DomainEventSink
from .pipelines.build import build_game_pipeline


def create_dbg_game(
    *,
    name: str,
    player_name: str,
    player_actor: str,
    world: WorldState,
    events: Optional[DomainEventSink] = None,
) -> DBGGame:
    """创建完整的游戏业务上下文（数据 + 唯一 pipeline）。

    ``player_name`` / ``player_actor`` 是构建玩家实体所需的领域身份；
    ``events`` 是应用层注入的领域事件出口，游戏本身不持有 PlayerSession。
    """
    dbg_game = DBGGame(
        name=name,
        player_name=player_name,
        player_actor=player_actor,
        world=world,
    )
    if events is not None:
        dbg_game.events = events
    dbg_game.pipeline = build_game_pipeline(dbg_game)
    return dbg_game
