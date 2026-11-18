"""游戏生命周期与唯一 pipeline 的运行时管理。"""

from loguru import logger

from .context import SRPGGame
from .pipelines import close_pipeline


###############################################################################################################################################
async def initialize_pipeline(srpg_game: SRPGGame) -> None:
    """初始化唯一 pipeline，并激活其中的反应式处理器。"""
    srpg_game.pipeline.activate_reactive_processors()
    await srpg_game.pipeline.initialize()


###############################################################################################################################################
def shutdown_pipeline(srpg_game: SRPGGame) -> None:
    """关闭唯一 pipeline 并清理资源。"""
    close_pipeline(srpg_game.pipeline)


###############################################################################################################################################
async def initialize_game(srpg_game: SRPGGame) -> None:
    logger.debug("Initializing game, setting up pipeline and world state...")
    await initialize_pipeline(srpg_game)


###############################################################################################################################################
def exit_game(srpg_game: SRPGGame) -> None:
    logger.debug("Exiting game, performing cleanup...")
    shutdown_pipeline(srpg_game)
