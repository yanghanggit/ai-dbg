"""ECS 运行时状态与 WorldState 快照之间的转换。"""

from loguru import logger

from ..context import SRPGGame
from ..entities import restore_context, serialize_context


def restore_from_snapshot(srpg_game: SRPGGame) -> SRPGGame:
    """从序列化数据中恢复游戏世界状态。"""
    assert len(srpg_game.world.entities) > 0, "游戏中没有实体，不能恢复游戏"
    assert len(srpg_game.ecs.entities) == 0, "游戏中有实体，不能恢复游戏"
    if (len(srpg_game.world.entities) == 0) or (len(srpg_game.ecs.entities) > 0):
        logger.warning(
            f"游戏中没有实体，不能恢复游戏，world.entities = {srpg_game.world.entities}, ecs.entities = {srpg_game.ecs.entities}"
        )
        return srpg_game
    restore_context(srpg_game, srpg_game.world.entities)
    return srpg_game


def flush_entities(srpg_game: SRPGGame) -> SRPGGame:
    """保存当前 ECS 状态到 WorldState 快照。"""
    assert len(srpg_game.ecs.entities) > 0, "游戏中没有实体，不能生成快照"
    srpg_game.world.entities = serialize_context(srpg_game)
    return srpg_game
