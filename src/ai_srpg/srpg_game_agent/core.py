"""游戏动作：新局、接管角色、对局列表、舞台名单、快照列表与离线推进。

每个动作只做一件事，互不隐式串联：``new`` 只装配世界，``bind`` 只改绑定，
两者可以任意组合。
"""

from typing import Dict, List, Optional

from loguru import logger

from ..game.entities.queries import get_actors_by_stage_as_names
from ..gameplay.offline import (
    BindActorOutcome,
    NewGameOutcome,
    OfflinePassOutcome,
    bind_actor,
    create_new_game,
    list_games,
    list_snapshots,
    load_or_create_game,
    run_offline_pass,
)
from ..models import GameSnapshotInfo, GameSummary


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
    "advance_game",
    "bind_actor_game",
    "create_and_initialize_game",
    "list_games_game",
    "snapshots_game",
    "stages_game",
]
