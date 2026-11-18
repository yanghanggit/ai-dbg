"""游戏动作：新局、场景名单、快照列表与离线推进。"""

from typing import Dict, List, Optional

from loguru import logger

from ..game.entities.queries import get_actors_by_stage_as_names
from ..models import GameSnapshotInfo
from ..services.offline_game import (
    NewGameOutcome,
    OfflinePassOutcome,
    create_new_game,
    list_snapshots,
    load_or_create_game,
    run_offline_pass,
)


###############################################################################
async def create_and_initialize_game(
    user: str,
    game: str,
    *,
    player_actor: Optional[str] = None,
    reset: bool = False,
) -> NewGameOutcome:
    """从蓝图新建一局，初始化 pipeline，并写入基线快照。"""
    outcome = await create_new_game(
        user,
        game,
        player_actor=player_actor,
        reset=reset,
    )
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
async def stages_game(
    user: str, game: str, snapshot_id: Optional[int]
) -> Dict[str, List[str]]:
    """读取快照并返回「场景 → 角色名」映射。"""
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
