"""游戏实例组装入口：构造上下文并装配默认 pipeline。"""

from ..models import PlayerSession, WorldState
from .context import DBGGame
from .pipelines.build import build_game_pipeline


def create_dbg_game(
    *,
    name: str,
    player_session: PlayerSession,
    world: WorldState,
) -> DBGGame:
    """创建完整的游戏业务上下文（数据 + 唯一 pipeline）。"""
    dbg_game = DBGGame(name=name, player_session=player_session, world=world)
    dbg_game.pipeline = build_game_pipeline(dbg_game)
    return dbg_game
