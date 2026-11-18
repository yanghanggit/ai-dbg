"""游戏领域上下文与组装入口。"""

from .assembly import create_srpg_game
from .context import SRPGGame

__all__ = ["SRPGGame", "create_srpg_game"]
