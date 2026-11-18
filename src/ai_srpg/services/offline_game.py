"""离线一局：从蓝图或数据库快照构造可运行的游戏实例。

CLI 没有房间与锁，因此这里只处理「读取 / 创建 / 保存」，不涉及 session。
运行 pass 复用 ``gameplay_runtime.run_pass``，与后台 job 共享快照与回滚语义。
"""

from typing import Optional

from ..game.context import SRPGGame
from ..game.lifecycle import (
    initialize_pipeline,
    rebuild_pipeline,
    snapshot_game,
)
from ..game.offline import create_game_from_blueprint, restore_game_from_snapshot
from ..models import GameSnapshot
from ..pgsql import append_game_snapshot, load_latest_game_snapshot
from ..pgsql.game_snapshot_operations import load_game_snapshot


###############################################################################
async def load_or_create_game(
    user_name: str,
    game_name: str,
    *,
    snapshot_id: Optional[int] = None,
    player_actor: Optional[str] = None,
) -> SRPGGame:
    """读取指定快照；没有快照时从蓝图新建，并写入基线快照。"""
    snapshot = _load_snapshot(user_name, game_name, snapshot_id)
    if snapshot is not None:
        game = restore_game_from_snapshot(game_name, snapshot)
        await rebuild_pipeline(game)
        return game

    if snapshot_id is not None:
        raise LookupError(
            f"找不到快照: user={user_name!r}, game={game_name!r}, id={snapshot_id}"
        )

    game = create_game_from_blueprint(
        user_name,
        game_name,
        player_actor=player_actor,
    )
    await initialize_pipeline(game)
    append_game_snapshot(user_name, snapshot_game(game))
    return game


###############################################################################
def save_game_snapshot(user_name: str, game: SRPGGame) -> int:
    """保存当前游戏状态，返回新快照 id。"""
    return append_game_snapshot(user_name, snapshot_game(game))


###############################################################################
def _load_snapshot(
    user_name: str,
    game_name: str,
    snapshot_id: Optional[int],
) -> Optional[GameSnapshot]:
    if snapshot_id is None:
        return load_latest_game_snapshot(user_name, game_name)
    return load_game_snapshot(
        snapshot_id,
        user_name=user_name,
        game_name=game_name,
    )


__all__ = ["load_or_create_game", "save_game_snapshot"]
