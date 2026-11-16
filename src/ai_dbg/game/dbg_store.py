"""
游戏存储模块 —— 统一 flush + save 操作

封装 flush_entities() → save_world() 的标准存储流程，
保证每次持久化前 ECS 运行时状态已同步到序列化模型。
"""

import asyncio
from pathlib import Path
from typing import Optional

from ..paths import WORLDS_DIR
from .dbg_game import DBGGame
from .game_lifecycle import (
    flush_entities,
)
from .world_persistence import save_world


def _store_game(dbg_game: DBGGame, save_dir: Optional[Path] = None) -> bool:
    """先刷新实体状态再持久化存档。"""
    flush_entities(dbg_game)
    return save_world(
        dbg_game.world,
        dbg_game.player_session,
        worlds_dir=WORLDS_DIR,
        save_dir=save_dir,
    )


async def store_game_async(dbg_game: DBGGame, save_dir: Optional[Path] = None) -> bool:
    """持久化存档的异步入口：把阻塞 I/O 移出事件循环线程。"""
    return await asyncio.to_thread(_store_game, dbg_game, save_dir)
