"""离线一局：按快照读取 / 创建 / 保存游戏，没有房间与锁。

快照归属键是 ``room_id``；离线没有房间，调用方传入的标识即当局的键。
"""

from dataclasses import dataclass
from typing import List, Optional

from ..entitas import Entity, PassResult, ProcessorObserver
from ..game.context import SRPGGame
from ..game.entities.player_binding import bind_player_actor
from ..game.entities.queries import get_actor_entity, list_actor_summaries
from ..game.events.sink import DomainEventSink
from ..game.lifecycle import (
    initialize_pipeline,
    rebuild_pipeline,
    snapshot_game,
)
from ..game.offline import create_game_from_blueprint, restore_game_from_snapshot
from ..models import (
    ActorPlanAction,
    ActorSummary,
    GameSnapshot,
    GameSnapshotInfo,
    GameSummary,
)
from ..pgsql import (
    append_game_snapshot,
    list_game_snapshot_ids,
    list_game_snapshots,
    list_game_summaries,
    load_latest_game_snapshot,
)
from ..pgsql.game_snapshot_operations import load_game_snapshot
from .runtime import run_pass


class GameAlreadyExistsError(RuntimeError):
    """``new`` 遇到已有快照且没有要求重建。"""

    def __init__(self, room_id: str, game_name: str, snapshot_count: int) -> None:
        super().__init__(
            f"房间 {room_id!r} 的游戏 {game_name!r} 已有 {snapshot_count} 个快照；如需从蓝图重建，请加 --reset（旧快照会保留）"
        )


@dataclass(frozen=True)
class NewGameOutcome:
    game: SRPGGame
    snapshot_id: int


@dataclass(frozen=True)
class BindActorOutcome:
    """一次接管的结果：谁接管了谁，落在哪个快照。"""

    user_name: str
    actor_name: str
    snapshot_id: int


@dataclass(frozen=True)
class PlanOutcome:
    """一次计划的结果：计划了谁，落在哪个快照。"""

    actors: List[str]
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
    room_id: str,
    game_name: str,
    *,
    reset: bool = False,
    events: Optional[DomainEventSink] = None,
) -> NewGameOutcome:
    """从蓝图新建一局并写入基线快照；``reset`` 允许覆盖已有对局语义。

    只装配世界，不绑定玩家——接管角色是独立的一步（``bind_actor``）。
    """
    if not reset and load_latest_game_snapshot(room_id, game_name) is not None:
        raise GameAlreadyExistsError(
            room_id,
            game_name,
            len(list_game_snapshot_ids(room_id, game_name)),
        )

    game = create_game_from_blueprint(game_name, events=events)
    await initialize_pipeline(game)
    snapshot_id = append_game_snapshot(room_id, snapshot_game(game))
    return NewGameOutcome(game=game, snapshot_id=snapshot_id)


###############################################################################
async def load_required_game(
    room_id: str,
    game_name: str,
    *,
    snapshot_id: Optional[int] = None,
    events: Optional[DomainEventSink] = None,
) -> SRPGGame:
    """读取已存在的对局；没有快照就报错，不隐式建局。"""
    snapshot = _load_snapshot(room_id, game_name, snapshot_id)
    if snapshot is None:
        if snapshot_id is not None:
            raise LookupError(
                f"找不到快照: room={room_id!r}, game={game_name!r}, id={snapshot_id}"
            )
        raise LookupError(
            f"找不到对局: room={room_id!r}, game={game_name!r}（先用 new 建局）"
        )
    game = restore_game_from_snapshot(game_name, snapshot, events=events)
    await rebuild_pipeline(game)
    return game


###############################################################################
async def load_or_create_game(
    room_id: str,
    game_name: str,
    *,
    snapshot_id: Optional[int] = None,
    events: Optional[DomainEventSink] = None,
) -> SRPGGame:
    """读取指定快照；没有快照时从蓝图新建，并写入基线快照。

    ``events`` 会注入到构造出的游戏实例，用于把领域事件接入会话历史等出口。
    """
    try:
        return await load_required_game(
            room_id, game_name, snapshot_id=snapshot_id, events=events
        )
    except LookupError:
        if snapshot_id is not None:
            raise

    outcome = await create_new_game(room_id, game_name, events=events)
    return outcome.game


###############################################################################
async def bind_actor(
    room_id: str,
    game_name: str,
    user_name: str,
    actor_name: str,
    *,
    snapshot_id: Optional[int] = None,
) -> BindActorOutcome:
    """让 ``user_name`` 接管 ``actor_name``，并把结果落成新快照。

    入场前的一次配置动作：不推进时间，不进 pipeline。
    """
    game = await load_required_game(room_id, game_name, snapshot_id=snapshot_id)
    entity = bind_player_actor(game, user_name, actor_name)
    new_snapshot_id = save_game_snapshot(room_id, game)
    return BindActorOutcome(
        user_name=user_name,
        actor_name=entity.name,
        snapshot_id=new_snapshot_id,
    )


###############################################################################
async def plan_actors(
    room_id: str,
    game_name: str,
    actor_names: List[str],
    *,
    snapshot_id: Optional[int] = None,
) -> PlanOutcome:
    """给指定角色挂上计划动作，跑一次 pass，把结果落成新快照。

    计划不改变世界状态：它只让角色想一遍，并把过程写进自己的记忆。
    """
    game = await load_required_game(room_id, game_name, snapshot_id=snapshot_id)
    actors = _require_actors(game, actor_names)
    for actor in actors:
        actor.replace(ActorPlanAction)
    outcome = await run_offline_pass(game, room_id)
    return PlanOutcome(
        actors=[actor.name for actor in actors],
        snapshot_id=outcome.snapshot_id,
    )


###############################################################################
async def list_actors(
    room_id: str, game_name: str, *, snapshot_id: Optional[int] = None
) -> List[ActorSummary]:
    """列出对局里的角色名册；对局不存在时报错，不隐式建局。"""
    game = await load_required_game(room_id, game_name, snapshot_id=snapshot_id)
    return list_actor_summaries(game)


###############################################################################
def list_games(room_id: str) -> List[GameSummary]:
    """列出房间（用户）下的所有对局，按最近更新倒序。"""
    return list_game_summaries(room_id)


###############################################################################
def save_game_snapshot(room_id: str, game: SRPGGame) -> int:
    """保存当前游戏状态，返回新快照 id。"""
    return append_game_snapshot(room_id, snapshot_game(game))


###############################################################################
async def run_offline_pass(
    game: SRPGGame,
    room_id: str,
    observer: Optional[ProcessorObserver] = None,
) -> OfflinePassOutcome:
    """执行一次 pass；成功后追加结果快照，保证 CLI 进程退出后状态仍可恢复。"""
    try:
        result = await run_pass(game, room_id, observer)
    except Exception as exc:
        raise OfflinePassFailed(exc) from exc
    snapshot_id = save_game_snapshot(room_id, game)
    return OfflinePassOutcome(result=result, snapshot_id=snapshot_id)


###############################################################################
def list_snapshots(
    room_id: str, game_name: str, *, limit: int = 20
) -> List[GameSnapshotInfo]:
    """列出快照元数据（时间倒序）。"""
    return list_game_snapshots(room_id, game_name, limit=limit)


###############################################################################
def _require_actors(game: SRPGGame, actor_names: List[str]) -> List[Entity]:
    actors: List[Entity] = []
    for actor_name in actor_names:
        actor = get_actor_entity(game, actor_name)
        if actor is None:
            raise LookupError(f"找不到角色实体: {actor_name}")
        actors.append(actor)
    return actors


###############################################################################
def _load_snapshot(
    room_id: str,
    game_name: str,
    snapshot_id: Optional[int],
) -> Optional[GameSnapshot]:
    if snapshot_id is None:
        return load_latest_game_snapshot(room_id, game_name)
    return load_game_snapshot(
        snapshot_id,
        room_id=room_id,
        game_name=game_name,
    )


__all__ = [
    "GameAlreadyExistsError",
    "PlanOutcome",
    "NewGameOutcome",
    "OfflinePassFailed",
    "OfflinePassOutcome",
    "create_new_game",
    "list_actors",
    "list_snapshots",
    "load_or_create_game",
    "plan_actors",
    "run_offline_pass",
    "save_game_snapshot",
]
