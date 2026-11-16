"""游戏生命周期与唯一 pipeline 的运行时管理。"""

from loguru import logger

from .context import DBGGame


###############################################################################################################################################
async def initialize_pipeline(dbg_game: DBGGame) -> None:
    """初始化唯一 pipeline，并激活其中的反应式处理器。"""
    dbg_game.pipeline.activate_reactive_processors()
    await dbg_game.pipeline.initialize()


###############################################################################################################################################
def shutdown_pipeline(dbg_game: DBGGame) -> None:
    """关闭唯一 pipeline 并清理资源。"""
    dbg_game.pipeline.shutdown()


###############################################################################################################################################
async def initialize_game(dbg_game: DBGGame) -> None:
    logger.debug("Initializing game, setting up pipeline and world state...")
    await initialize_pipeline(dbg_game)


###############################################################################################################################################
def exit_game(dbg_game: DBGGame) -> None:
    logger.debug("Exiting game, performing cleanup...")
    shutdown_pipeline(dbg_game)
