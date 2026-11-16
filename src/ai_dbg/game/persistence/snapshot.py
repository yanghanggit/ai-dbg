"""ECS 运行时状态与 WorldState 快照之间的转换。"""

from loguru import logger

from ..context import DBGGame
from ..entities import restore_context, serialize_context


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


def flush_entities(dbg_game: DBGGame) -> DBGGame:
    """保存当前 ECS 状态到 WorldState 快照。"""
    assert len(dbg_game.ecs.entities) > 0, "游戏中没有实体，不能生成快照"
    dbg_game.world.entities = serialize_context(dbg_game)
    return dbg_game
