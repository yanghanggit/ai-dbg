"""一次 pass 的编排：执行前快照 → 运行 → 失败回滚，成功后追加结果快照。

失败路径不追加结果快照，因此「最新快照 = 当前状态」始终成立。
"""

from typing import Optional

from loguru import logger

from ..entitas.pass_result import PassResult
from ..entitas.processor_interfaces import ProcessorObserver
from ..game.context import SRPGGame
from ..game.lifecycle import rollback_game, snapshot_game
from ..game.pipelines import process_pipeline
from ..llm.call_context import llm_call_trace
from ..pgsql import append_game_snapshot
from ..session.errors import GameNotFoundError
from ..session.job_context import get_current_job
from ..session.room import Room
from ..session.runtime import get_runtime_room_registry


###############################################################################
async def run_game_pass(
    room_id: str, observer: Optional[ProcessorObserver] = None
) -> PassResult:
    """后台 job 的执行入口：进入房间锁并跑一次 pass，成功后追加结果快照。

    必须从 job 体调用，不要在已持有 ``room_registry.acquire`` 的代码里调用
    （房间锁不可重入）。
    """
    async with get_runtime_room_registry().acquire(room_id) as room:
        result = await run_room_pass(room, observer=observer)

        game = room.game
        assert game is not None, "pass 成功后房间必然仍有游戏"
        snapshot_id = append_game_snapshot(room_id, snapshot_game(game))
        logger.debug(f"pass result snapshot saved: room={room_id}, id={snapshot_id}")
        return result


###############################################################################
async def run_pass(
    game: SRPGGame,
    room_id: str,
    observer: Optional[ProcessorObserver] = None,
) -> PassResult:
    """对任意游戏实例执行一次 pass：快照 → 执行 → 失败回滚。

    不依赖房间或锁；CLI 离线运行与后台 job 共用这一层。
    """
    if observer is None:
        observer = get_current_job()

    snapshot = snapshot_game(game)
    snapshot_id = append_game_snapshot(room_id, snapshot)
    logger.debug(f"pass snapshot saved: room={room_id}, id={snapshot_id}")

    with llm_call_trace(
        user=room_id,
        game=game.name,
        snapshot_id=snapshot_id,
    ):
        try:
            return await process_pipeline(game.pipeline, observer)
        except BaseException:
            try:
                await rollback_game(game, snapshot)
            except Exception:
                logger.exception(f"回滚失败: room={room_id}, snapshot_id={snapshot_id}")
            raise


###############################################################################
async def run_room_pass(
    room: Room, observer: Optional[ProcessorObserver] = None
) -> PassResult:
    """在已持有房间锁的前提下执行一次 pass。"""
    game = room.game
    if game is None:
        raise GameNotFoundError(room_id=room.room_id)

    if observer is None:
        observer = get_current_job()

    current_job = get_current_job()
    with llm_call_trace(
        scope="room",
        scope_id=room.room_id,
        user=room.owner,
        game=game.name,
        room=room.room_id,
        job_id=current_job.job_id if current_job is not None else None,
    ):
        return await run_pass(game, room.room_id, observer)
