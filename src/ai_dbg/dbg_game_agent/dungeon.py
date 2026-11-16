"""副本生命周期动作。

包含副本模式下的关卡推进与退出等通用生命周期函数（不依赖具体房间类型）。
"""

from pathlib import Path

from loguru import logger

from ai_dbg.game.dbg_game import DBGGame
from ai_dbg.game.dbg_store import store_game_async
from ai_dbg.game.game_dungeon import (
    current_dungeon,
    current_dungeon_combat_room,
    is_current_room_dungeon_combat,
    is_current_room_dungeon_opening,
    is_player_in_dungeon_stage,
)
from ai_dbg.models import PlayerSession, WorldState
from ai_dbg.services.dungeon_advance_action import (
    advance_dungeon,
)
from ai_dbg.services.dungeon_enter_action import (
    enter_dungeon,
)
from ai_dbg.services.dungeon_exit_action import (
    exit_dungeon,
)
from ai_dbg.services.dungeon_setup_action import (
    setup_dungeon,
)
from ai_dbg.services.dungeon_teardown_action import (
    teardown_dungeon,
)

from .core import restore_game


###############################################################################
async def next_dungeon_game(
    world: WorldState,
    player_session: PlayerSession,
    save_dir: Path,
) -> DBGGame:
    """进入副本下一关并归档。需前一关已胜利（或为非战斗房间）且存在下一关。"""

    # 创建 DBGGame 实例并从快照恢复游戏状态
    terminal_game = await restore_game(world, player_session)

    # 状态守卫：玩家必须处于副本场景中（与 API 的 _validate_dungeon_prerequisites 对齐）
    if not is_player_in_dungeon_stage(terminal_game):
        logger.error("next-dungeon 只能在副本场景中使用")
        return terminal_game

    # 若当前为战斗房间，需确认战斗已结束且胜利
    if is_current_room_dungeon_combat(terminal_game):
        if not current_dungeon_combat_room(terminal_game).combat.is_post_combat:
            logger.error("next-dungeon 只能在战斗结束后使用")
            return terminal_game

        if current_dungeon_combat_room(terminal_game).combat.is_lost:
            logger.info("英雄失败，应该返回营地")
            return terminal_game

        if not current_dungeon_combat_room(terminal_game).combat.is_won:
            assert False, "不可能出现的情况！"

    elif is_current_room_dungeon_opening(terminal_game):
        logger.info("当前为非战斗房间，直接进入下一关")

    # 获取下一房间索引和房间实例，确保存在下一房间，否则无法推进副本
    next_room_index = current_dungeon(terminal_game).current_room_index + 1
    next_room = current_dungeon(terminal_game).get_room(next_room_index)
    if next_room is None:
        logger.error("副本前进失败，没有更多房间")
        return terminal_game

    # 推进副本到下一房间，更新当前房间索引和状态
    success, msg = await advance_dungeon(terminal_game, current_dungeon(terminal_game))
    if not success:
        logger.error(f"advance_dungeon 失败: {msg}")
        return terminal_game

    # 与 API 对齐：advance 仅推进房间，不自动初始化新房间。
    # 新房间的初始化由 agent 根据房间类型显式调用 combat-init 或 opening-init。
    if is_current_room_dungeon_combat(terminal_game):
        logger.info("已进入战斗房间，下一步请使用 combat-init 初始化战斗")
    elif is_current_room_dungeon_opening(terminal_game):
        logger.info("已进入开场房间，下一步请使用 opening-init 初始化开场房间")
    else:
        current_room = current_dungeon(terminal_game).current_room
        assert current_room is not None, f"当前房间为 {current_room!r}，无法处理"
        logger.error(f"未知房间类型 {current_room.type!r}，无法处理")
        return terminal_game

    # 最后归档
    await store_game_async(terminal_game, save_dir)

    # 返回更新后的游戏实例
    return terminal_game


###############################################################################
async def enter_dungeon_game(
    world: WorldState,
    player_session: PlayerSession,
    dungeon_name: str,
    save_dir: Path,
) -> DBGGame:
    """进入指定副本第一关并归档。需处于大厅。"""

    # 创建 DBGGame 实例并从快照恢复游戏状态
    terminal_game = await restore_game(world, player_session)

    # 创建副本实体
    success, error_detail = setup_dungeon(terminal_game, dungeon_name)
    if not success:
        logger.error(f"副本实体创建失败: {error_detail}")
        return terminal_game

    # 进入副本第一关
    success, error_detail = enter_dungeon(terminal_game, current_dungeon(terminal_game))
    if not success:
        logger.error(f"进入副本第一关失败: {error_detail}")
        return terminal_game

    # 与 API 对齐：enter 仅进入房间，不自动初始化房间。
    # 房间初始化由 agent 根据房间类型显式调用 combat-init 或 opening-init。
    if is_current_room_dungeon_combat(terminal_game):
        logger.info("已进入战斗房间，下一步请使用 combat-init 初始化战斗")
    elif is_current_room_dungeon_opening(terminal_game):
        logger.info("已进入开场房间，下一步请使用 opening-init 初始化开场房间")
    else:
        current_room = current_dungeon(terminal_game).current_room
        assert current_room is not None, f"当前房间为 {current_room!r}，无法处理"
        logger.error(f"未知房间类型 {current_room.type!r}，无法处理")
        return terminal_game

    # 最后归档
    await store_game_async(terminal_game, save_dir)

    # 返回更新后的游戏实例
    return terminal_game


###############################################################################
async def exit_dungeon_game(
    world: WorldState,
    player_session: PlayerSession,
    save_dir: Path,
) -> DBGGame:
    """结束副本返回大厅并归档。需战斗已结束（无论胜负），非战斗房间可直接退出。"""

    # 创建 DBGGame 实例并从快照恢复游戏状态
    terminal_game = await restore_game(world, player_session)

    # 状态守卫：玩家必须处于副本场景中（与 API 的 _validate_dungeon_prerequisites 对齐）
    if not is_player_in_dungeon_stage(terminal_game):
        logger.error("exit-dungeon 只能在副本场景中使用")
        return terminal_game

    # 若当前为战斗房间，状态守卫：只能在战斗结束后使用
    if is_current_room_dungeon_combat(terminal_game):
        if not current_dungeon_combat_room(terminal_game).combat.is_post_combat:
            logger.error("exit-dungeon 只能在战斗结束后使用")
            return terminal_game

    elif is_current_room_dungeon_opening(terminal_game):
        logger.info("当前为非战斗房间，直接退出副本")

    # 执行退出副本流程，返回大厅
    success, msg = exit_dungeon(terminal_game, terminal_game.world.dungeon)
    if not success:
        logger.error(f"exit_dungeon 失败: {msg}")
        return terminal_game

    # 销毁副本实体并重置副本数据
    teardown_dungeon(terminal_game, terminal_game.world.dungeon)

    # 最后归档
    await store_game_async(terminal_game, save_dir)

    # 返回更新后的游戏实例
    return terminal_game
