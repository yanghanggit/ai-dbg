"""游戏存储入口：先刷新 ECS，再写入世界快照。"""

import asyncio
from pathlib import Path
from typing import Optional

from ...paths import WORLDS_DIR
from ..context import SRPGGame
from .save import save_world
from .snapshot import flush_entities


def _store_game(srpg_game: SRPGGame, save_dir: Optional[Path] = None) -> bool:
    """先刷新实体状态再持久化存档。"""
    flush_entities(srpg_game)
    return save_world(
        srpg_game.world,
        worlds_dir=WORLDS_DIR,
        save_dir=save_dir,
        user_name=srpg_game.player_name,
        game_name=srpg_game.name,
    )


async def store_game_async(
    srpg_game: SRPGGame, save_dir: Optional[Path] = None
) -> bool:
    """持久化存档的异步入口：写盘失败即抛异常，避免 job 假装成功。"""
    saved = await asyncio.to_thread(_store_game, srpg_game, save_dir)
    if not saved:
        raise RuntimeError(
            f"世界存档失败: user={srpg_game.player_name}, game={srpg_game.name}"
        )
    return True
