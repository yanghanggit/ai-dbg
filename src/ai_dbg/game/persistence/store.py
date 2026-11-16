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
    """持久化存档的异步入口：把阻塞 I/O 移出事件循环线程。"""
    return await asyncio.to_thread(_store_game, dbg_game, save_dir)
