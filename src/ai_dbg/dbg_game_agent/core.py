"""游戏动作基础设施层。

提供游戏实例的创建与从存档复位的共享入口，供各动作模块 import 使用。
"""

from pathlib import Path
from typing import Dict, List

from loguru import logger

from ai_dbg.game.assembly import create_dbg_game
from ai_dbg.game.context import DBGGame
from ai_dbg.game.entities import (
    build_from_blueprint,
    get_actors_by_stage_as_names,
)
from ai_dbg.game.lifecycle import (
    initialize_game,
)
from ai_dbg.game.persistence.snapshot import restore_from_snapshot
from ai_dbg.game.persistence.store import store_game_async
from ai_dbg.models import Blueprint, PlayerSession, WorldState
from ai_dbg.paths import BLUEPRINTS_DIR
from ai_dbg.services.dungeon_enter_action import enter_dungeon
from ai_dbg.services.dungeon_setup_action import setup_dungeon


###############################################################################
async def create_and_initialize_game(
    user: str, game: str, dungeon_name: str, save_dir: Path
) -> DBGGame:
    """从蓝图文件和副本文件创建并初始化新游戏实例，完成后归档。"""

    # 从 JSON 文件加载蓝图
    blueprint_path = BLUEPRINTS_DIR / f"{game}.json"
    assert blueprint_path.exists(), f"蓝图文件不存在: {blueprint_path}"
    world_blueprint = Blueprint.model_validate_json(
        blueprint_path.read_text(encoding="utf-8")
    )
    assert world_blueprint is not None, "world blueprint 反序列化失败"

    # 创建游戏世界数据实例
    world_data = WorldState(
        entity_counter=1000,
        entities={},
        agent_memories={},
        blueprint=world_blueprint,
    )

    # 创建 DBGGame 实例并初始化
    assert world_data is not None, "WorldState data must exist to create a game"
    terminal_game = create_dbg_game(
        name=game,
        player_session=PlayerSession(
            name=user,
            actor=world_data.blueprint.player_actor,
            game=game,
        ),
        world=world_data,
    )

    # 创建实体数据（敌人和场景），并初始化游戏状态
    assert len(terminal_game.world.entities) == 0, "新游戏创建时不应该有实体数据！"
    build_from_blueprint(terminal_game)

    # 初始化游戏状态，包括场景描述、初始状态效果、创建新回合等
    await initialize_game(terminal_game)

    # 加载预置副本并直接进入首间：新局不再经过大厅中转
    success, error_detail = setup_dungeon(terminal_game, dungeon_name)
    if not success:
        raise RuntimeError(f"副本实体创建失败: {error_detail}")
    success, error_detail = enter_dungeon(terminal_game)
    if not success:
        raise RuntimeError(f"进入副本失败: {error_detail}")

    logger.info(
        f"游戏创建并初始化完成：user={user}, game={game}, dungeon={dungeon_name}"
    )

    # 持久化游戏世界数据到存档目录，并启用 gzip 快照功能
    await store_game_async(terminal_game, save_dir)

    # 返回游戏实例
    return terminal_game


###############################################################################
async def stages_game(
    world: WorldState,
    player_session: PlayerSession,
) -> Dict[str, List[str]]:
    """返回当前各场景内角色名单（只读，不归档）。"""
    terminal_game = await restore_game(world, player_session)
    return get_actors_by_stage_as_names(terminal_game)


###############################################################################
async def restore_game(
    world: WorldState,
    player_session: PlayerSession,
) -> DBGGame:
    """从 WorldState/PlayerSession 快照还原 DBGGame 实例。所有动作命令的共享入口。"""

    # 创建 DBGGame 实例并从快照恢复游戏状态
    game = str(world.blueprint.name)
    terminal_game = create_dbg_game(
        name=game,
        player_session=player_session,
        world=world,
    )

    # 从快照恢复游戏状态，并初始化游戏状态，包括场景描述、初始状态效果、创建新回合等
    restore_from_snapshot(terminal_game)

    # 初始化游戏状态，包括场景描述、初始状态效果、创建新回合等
    await initialize_game(terminal_game)
    logger.info(f"游戏已从存档恢复：user={player_session.name}, game={game}")

    # 返回游戏实例
    return terminal_game
