"""游戏生命周期、快照与 pipeline 管理。"""

from loguru import logger

from .dbg_game import DBGGame
from .game_entities import restore_context, serialize_context
from .game_process_pipeline import RPGGameProcessPipeline


###############################################################################################################################################
def register_pipeline(dbg_game: DBGGame, pipeline: RPGGameProcessPipeline) -> None:
    dbg_game.pipelines.append(pipeline)


###############################################################################################################################################
async def initialize_pipelines(dbg_game: DBGGame) -> None:
    """初始化所有已注册的管道，激活反应式处理器。"""
    for pipeline in dbg_game.pipelines:
        pipeline.activate_reactive_processors()
        await pipeline.initialize()


###############################################################################################################################################
def shutdown_pipelines(dbg_game: DBGGame) -> None:
    """关闭所有管道并清空管道列表。"""
    for pipeline in dbg_game.pipelines:
        pipeline.shutdown()
    dbg_game.pipelines = []


###############################################################################################################################################
async def initialize_game(dbg_game: DBGGame) -> None:
    logger.debug("Initializing game, setting up pipelines and world state...")
    await initialize_pipelines(dbg_game)


###############################################################################################################################################
def exit_game(dbg_game: DBGGame) -> None:
    logger.debug("Exiting game, performing cleanup...")
    shutdown_pipelines(dbg_game)


###############################################################################################################################################
def restore_from_snapshot(dbg_game: DBGGame) -> DBGGame:
    """从序列化数据中恢复游戏世界状态。"""
    assert len(dbg_game.world.entities) > 0, "游戏中没有实体，不能恢复游戏"
    assert len(dbg_game.ecs.entities) == 0, "游戏中有实体，不能恢复游戏"
    if (len(dbg_game.world.entities) == 0) or (len(dbg_game.ecs.entities) > 0):
        logger.warning(
            f"游戏中没有实体，不能恢复游戏，world.entities = {dbg_game.world.entities}, ecs.entities = {dbg_game.ecs.entities}"
        )
        return dbg_game
    restore_context(dbg_game, dbg_game.world.entities)
    return dbg_game


###############################################################################################################################################
def flush_entities(dbg_game: DBGGame) -> DBGGame:
    """保存当前 ECS 状态到 WorldState 快照。"""
    assert len(dbg_game.ecs.entities) > 0, "游戏中没有实体，不能生成快照"
    dbg_game.world.entities = serialize_context(dbg_game)
    return dbg_game
