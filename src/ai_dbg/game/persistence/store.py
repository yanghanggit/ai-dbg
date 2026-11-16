"""游戏存储入口：先刷新 ECS，再写入世界快照。"""

import asyncio
from pathlib import Path
from typing import Optional

from ...paths import WORLDS_DIR
from ..context import DBGGame
from .save import save_world
from .snapshot import flush_entities


def _store_game(dbg_game: DBGGame, save_dir: Optional[Path] = None) -> bool:
    """先刷新实体状态再持久化存档。"""
    flush_entities(dbg_game)
    return save_world(
        dbg_game.world,
        worlds_dir=WORLDS_DIR,
        save_dir=save_dir,
        user_name=dbg_game.player_name,
        game_name=dbg_game.name,
    )


async def store_game_async(dbg_game: DBGGame, save_dir: Optional[Path] = None) -> bool:
    """持久化存档的异步入口：写盘失败即抛异常，避免 job 假装成功。"""
    saved = await asyncio.to_thread(_store_game, dbg_game, save_dir)
    if not saved:
        raise RuntimeError(
            f"世界存档失败: user={dbg_game.player_name}, game={dbg_game.name}"
        )
    return True
