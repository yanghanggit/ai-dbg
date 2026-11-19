"""游戏动作：新局、接管角色、对局列表、舞台名单、快照列表与离线推进。

每个动作只做一件事，互不隐式串联：``new`` 只装配世界，``bind`` 只改绑定，
两者可以任意组合。
"""

from pathlib import Path
from typing import Dict, List, Optional, Sequence

from loguru import logger

from ..entitas.components import Component
from ..game.entities.queries import get_actors_by_stage_as_names
from ..gameplay.offline import (
    BindActorOutcome,
    CommandOutcome,
    MemoryDumpOutcome,
    NewGameOutcome,
    OfflinePassOutcome,
    PlanOutcome,
    bind_actor,
    command_actor,
    create_new_game,
    dump_game_memories,
    list_actors,
    list_games,
    list_snapshots,
    load_or_create_game,
    plan_actors,
    run_offline_pass,
)
from ..models import ActorSummary, GameSnapshotInfo, GameSummary


###############################################################################
async def create_and_initialize_game(
    user: str,
    game: str,
    *,
    reset: bool = False,
) -> NewGameOutcome:
    """从蓝图新建一局，初始化 pipeline，并写入基线快照。"""
    outcome = await create_new_game(user, game, reset=reset)
    logger.info(
        "new game: user={}, game={}, entities={}, snapshot_id={}".format(
            user,
            game,
            outcome.game.entity_count,
            outcome.snapshot_id,
        )
    )
    return outcome


###############################################################################
async def bind_actor_game(
    user: str,
    game: str,
    actor_name: str,
    snapshot_id: Optional[int] = None,
) -> BindActorOutcome:
    """让该玩家接管一个已有角色，并写入结果快照。"""
    outcome = await bind_actor(user, game, user, actor_name, snapshot_id=snapshot_id)
    logger.info(
        "bind actor: user={}, game={}, actor={}, snapshot_id={}".format(
            user, game, outcome.actor_name, outcome.snapshot_id
        )
    )
    return outcome


###############################################################################
def list_games_game(user: str) -> List[GameSummary]:
    """列出该玩家的所有对局。"""
    return list_games(user)


###############################################################################
async def stages_game(
    user: str, game: str, snapshot_id: Optional[int]
) -> Dict[str, List[str]]:
    """读取快照并返回「舞台 → 角色名」映射。"""
    srpg_game = await load_or_create_game(user, game, snapshot_id=snapshot_id)
    mapping = get_actors_by_stage_as_names(srpg_game)
    return {
        stage_name: sorted(actor_names) for stage_name, actor_names in mapping.items()
    }


###############################################################################
async def command_actor_game(
    user: str,
    game: str,
    actor: str,
    action: Component,
    *,
    force: bool = False,
    snapshot_id: Optional[int] = None,
) -> CommandOutcome:
    """接管一个角色：校验、挂动作、跑一次 pass。"""
    outcome = await command_actor(
        user, game, user, actor, action, force=force, snapshot_id=snapshot_id
    )
    logger.info(
        "command actor: user={}, actor={}, action={}, at={}, snapshot_id={}".format(
            user,
            outcome.actor_name,
            outcome.command,
            outcome.location,
            outcome.snapshot_id,
        )
    )
    return outcome


###############################################################################
async def actors_game(
    user: str, game: str, snapshot_id: Optional[int]
) -> List[ActorSummary]:
    """读取快照并返回角色名册。"""
    return await list_actors(user, game, snapshot_id=snapshot_id)


###############################################################################
async def plan_game(
    user: str, game: str, actors: List[str], snapshot_id: Optional[int]
) -> PlanOutcome:
    """让一个或多个角色做本轮计划，并写入结果快照。"""
    outcome = await plan_actors(user, game, actors, snapshot_id=snapshot_id)
    logger.info(
        "plan actors: user={}, game={}, actors={}, snapshot_id={}".format(
            user, game, ", ".join(outcome.actors), outcome.snapshot_id
        )
    )
    return outcome


###############################################################################
async def memories_game(
    user: str,
    game: str,
    names: Optional[Sequence[str]] = None,
    *,
    snapshot_id: Optional[int] = None,
    directory: Optional[Path] = None,
) -> MemoryDumpOutcome:
    """导出记忆到 markdown；``names`` 为空导出全部实体。"""
    outcome = await dump_game_memories(
        user, game, names=names, snapshot_id=snapshot_id, directory=directory
    )
    logger.info(
        "dump memories: user={}, game={}, names={}, directory={}, entities={}, messages={}".format(
            user,
            game,
            ", ".join(names) if names else "全部",
            outcome.directory,
            outcome.entity_count,
            outcome.message_count,
        )
    )
    return outcome


###############################################################################
async def snapshots_game(
    user: str, game: str, *, limit: int = 20
) -> List[GameSnapshotInfo]:
    """列出某用户某局游戏的快照元数据。"""
    return list_snapshots(user, game, limit=limit)


###############################################################################
async def advance_game(
    user: str, game: str, snapshot_id: Optional[int]
) -> OfflinePassOutcome:
    """加载指定快照，执行一次 pass，并在成功后保存结果快照。"""
    srpg_game = await load_or_create_game(user, game, snapshot_id=snapshot_id)
    return await run_offline_pass(srpg_game, user)


###############################################################################
__all__ = [
    "actors_game",
    "command_actor_game",
    "advance_game",
    "bind_actor_game",
    "create_and_initialize_game",
    "list_games_game",
    "plan_game",
    "snapshots_game",
    "stages_game",
]
