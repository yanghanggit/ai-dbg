"""离线一局：从蓝图或数据库快照构造可运行的游戏实例。

CLI 没有房间与锁，因此这里只处理「读取 / 创建 / 保存」，不涉及 session。
运行 pass 复用 ``gameplay_runtime.run_pass``，与后台 job 共享快照与回滚语义。
"""

from dataclasses import dataclass
from typing import List, Optional

from ..entitas import PassResult, ProcessorObserver
from ..game.context import SRPGGame
from ..game.lifecycle import (
    initialize_pipeline,
    rebuild_pipeline,
    snapshot_game,
)
from ..game.offline import create_game_from_blueprint, restore_game_from_snapshot
from ..models import GameSnapshot, GameSnapshotInfo
from ..pgsql import (
    append_game_snapshot,
    list_game_snapshot_ids,
    list_game_snapshots,
    load_latest_game_snapshot,
)
from ..pgsql.game_snapshot_operations import load_game_snapshot
from .gameplay_runtime import run_pass


class GameAlreadyExistsError(RuntimeError):
    """``new`` 遇到已有快照且没有要求重建。"""

    def __init__(self, user_name: str, game_name: str, snapshot_count: int) -> None:
        super().__init__(
            f"用户 {user_name!r} 的游戏 {game_name!r} 已有 {snapshot_count} 个快照；如需从蓝图重建，请加 --reset（旧快照会保留）"
        )


@dataclass(frozen=True)
class NewGameOutcome:
    game: SRPGGame
    snapshot_id: int


@dataclass(frozen=True)
class OfflinePassOutcome:
    result: PassResult
    snapshot_id: int


class OfflinePassFailed(RuntimeError):
    """离线 pass 失败；调用方据此区分「加载失败」与「已回滚」。"""

    def __init__(self, cause: BaseException) -> None:
        super().__init__(str(cause))
        self.cause = cause


###############################################################################
async def create_new_game(
    user_name: str,
    game_name: str,
    *,
    player_actor: Optional[str] = None,
    reset: bool = False,
) -> NewGameOutcome:
    """从蓝图新建一局并写入基线快照；``reset`` 允许覆盖已有对局语义。"""
    if not reset and load_latest_game_snapshot(user_name, game_name) is not None:
        raise GameAlreadyExistsError(
            user_name,
            game_name,
            len(list_game_snapshot_ids(user_name, game_name)),
        )

    game = create_game_from_blueprint(
        user_name,
        game_name,
        player_actor=player_actor,
    )
    await initialize_pipeline(game)
    snapshot_id = append_game_snapshot(user_name, snapshot_game(game))
    return NewGameOutcome(game=game, snapshot_id=snapshot_id)


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

    outcome = await create_new_game(
        user_name,
        game_name,
        player_actor=player_actor,
    )
    return outcome.game


###############################################################################
def save_game_snapshot(user_name: str, game: SRPGGame) -> int:
    """保存当前游戏状态，返回新快照 id。"""
    return append_game_snapshot(user_name, snapshot_game(game))


###############################################################################
async def run_offline_pass(
    game: SRPGGame,
    user_name: str,
    observer: Optional[ProcessorObserver] = None,
) -> OfflinePassOutcome:
    """执行一次 pass；成功后追加结果快照，保证 CLI 进程退出后状态仍可恢复。"""
    try:
        result = await run_pass(game, user_name, observer)
    except Exception as exc:
        raise OfflinePassFailed(exc) from exc
    snapshot_id = save_game_snapshot(user_name, game)
    return OfflinePassOutcome(result=result, snapshot_id=snapshot_id)


###############################################################################
def list_snapshots(
    user_name: str, game_name: str, *, limit: int = 20
) -> List[GameSnapshotInfo]:
    """列出快照元数据（时间倒序）。"""
    return list_game_snapshots(user_name, game_name, limit=limit)


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


__all__ = [
    "GameAlreadyExistsError",
    "NewGameOutcome",
    "OfflinePassFailed",
    "OfflinePassOutcome",
    "create_new_game",
    "list_snapshots",
    "load_or_create_game",
    "run_offline_pass",
    "save_game_snapshot",
]
