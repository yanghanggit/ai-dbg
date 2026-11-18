"""
上下文压缩 job 模块
"""

from loguru import logger
from procrastinate import JobContext

from ..game.context import SRPGGame
from ..game.persistence.store import store_game_async
from ..job_context import get_current_job
from ..pgsql import procrastinate_app
from .compact_action import activate_compact_context
from .game_server_runtime import get_runtime_game_server
from .job_runtime import job_task


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
@job_task(action="compact_context")
async def execute_compact_context_job(
    context: JobContext,
    user_name: str,
    target_name: str,
) -> None:
    """执行手动上下文压缩 job"""
    job_id = context.job.id
    assert job_id is not None, "运行中的 job 必然有 job id"
    try:
        logger.info(f"🚀 上下文压缩 job 开始: job_id={job_id}, user={user_name}")

        game_server = get_runtime_game_server()

        async with game_server.acquire(user_name) as room:

            rpg_game = room.game
            if rpg_game is None:
                raise ValueError(f"游戏实例不存在: user={user_name}")
            assert isinstance(rpg_game, SRPGGame), "Invalid game type"

            # 激活手动压缩动作
            success, message = activate_compact_context(rpg_game, target_name)
            if not success:
                raise ValueError(message)

            # 执行全局 pipeline，由 CompactContextActionSystem 处理手动触发的压缩动作
            await rpg_game.pipeline.process(get_current_job())

            # 存档压缩后的世界状态，便于调试和回放
            await store_game_async(rpg_game)

        logger.info(f"✅ 上下文压缩 job 完成: job_id={job_id}, user={user_name}")

    except Exception as e:
        logger.error(
            f"❌ 上下文压缩 job 失败: job_id={job_id}, user={user_name}, error={e}"
        )
        raise
