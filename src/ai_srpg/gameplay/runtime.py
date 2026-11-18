"""一次游戏 pass 的运行时编排：快照 → 执行 → 失败回滚。

放在编排层而不是 ``process_pipeline``：ECS 运行辅助不应认识数据库，
快照的保存时机、失败后的回滚、房间锁的获取都属于应用编排。

粒度约定
--------
* 一个 pass 开始时追加一条整块快照（append-only 历史）；
* pass 正常结束（含 ``StopPipeline``）不回滚，快照保留为历史；
* pass 抛异常时把 ECS 与 agent 记忆一起回滚到该快照，再把原异常上抛；
* 回滚本身失败只记录，不覆盖原始异常，便于定位首个错误。
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
from ..session.room import PlayerRoom
from ..session.runtime import get_runtime_game_server


###############################################################################
async def run_game_pass(
    user_name: str, observer: Optional[ProcessorObserver] = None
) -> PassResult:
    """后台 job 的执行入口：进入房间锁并跑一次 pass。

    必须从 job 体调用，不要嵌套在已持有 ``game_server.acquire`` 的代码里，
    否则会重复获取同一把非重入的房间锁。
    """
    async with get_runtime_game_server().acquire(user_name) as room:
        return await run_room_pass(room, observer=observer)


###############################################################################
async def run_pass(
    game: SRPGGame,
    user_name: str,
    observer: Optional[ProcessorObserver] = None,
) -> PassResult:
    """对任意游戏实例执行一次 pass：快照 → 执行 → 失败回滚。

    不依赖房间或锁；CLI 离线运行与后台 job 共用这一层。
    """
    if observer is None:
        observer = get_current_job()

    snapshot = snapshot_game(game)
    snapshot_id = append_game_snapshot(user_name, snapshot)
    logger.debug(f"pass snapshot saved: user={user_name}, id={snapshot_id}")

    with llm_call_trace(
        user=user_name,
        game=game.name,
        snapshot_id=snapshot_id,
    ):
        try:
            return await process_pipeline(game.pipeline, observer)
        except BaseException:
            try:
                await rollback_game(game, snapshot)
            except Exception:
                logger.exception(
                    f"回滚失败: user={user_name}, snapshot_id={snapshot_id}"
                )
            raise


###############################################################################
async def run_room_pass(
    room: PlayerRoom, observer: Optional[ProcessorObserver] = None
) -> PassResult:
    """在已持有房间锁的前提下执行一次 pass。"""
    game = room.game
    if game is None:
        raise GameNotFoundError(user_name=room.username)

    if observer is None:
        observer = get_current_job()

    current_job = get_current_job()
    with llm_call_trace(
        scope="room",
        scope_id=room.username,
        user=room.username,
        game=game.name,
        room=room.username,
        job_id=current_job.job_id if current_job is not None else None,
    ):
        return await run_pass(game, room.username, observer)
