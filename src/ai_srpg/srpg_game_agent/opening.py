"""副本开场房间动作：开场初始化（叙事 + 环境注入）。"""

from pathlib import Path

from loguru import logger

from ai_srpg.game.context import SRPGGame
from ai_srpg.game.dungeon import (
    is_current_room_dungeon_opening,
)
from ai_srpg.game.persistence.store import store_game_async
from ai_srpg.game.pipelines import process_pipeline
from ai_srpg.models import PlayerSession, WorldState

from .core import restore_game


###############################################################################
async def init_opening_game(
    world: WorldState,
    player_session: PlayerSession,
    save_dir: Path,
) -> SRPGGame:
    """初始化开场房间（叙事 + 环境）并归档。需当前处于开场房间（管道按消息标记幂等）。"""

    # 创建 SRPGGame 实例并从快照恢复游戏状态
    terminal_game = await restore_game(world, player_session)

    # 状态守卫：只能在开场房间使用
    if not is_current_room_dungeon_opening(terminal_game):
        logger.error("opening-init 只能在开场房间中使用")
        return terminal_game

    # 推动全局 pipeline（各 system 自守卫；开场初始化按消息标记幂等）
    await process_pipeline(terminal_game.pipeline, None)

    # 最后归档
    await store_game_async(terminal_game, save_dir)
    return terminal_game
