"""副本生命周期 job 模块"""

from loguru import logger
from procrastinate import JobContext

from ..game.context import DBGGame
from ..game.persistence.store import store_game_async
from ..pgsql import procrastinate_app
from .dungeon_exit_action import (
    exit_dungeon,
)
from .dungeon_teardown_action import (
    teardown_dungeon,
)
from .game_server_runtime import get_runtime_game_server
from .job_runtime import job_task


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
@job_task(action="exit_dungeon")
async def execute_exit_dungeon_job(
    context: JobContext,
    user_name: str,
) -> None:
    """执行退出副本 job（返回大厅 + 实体销毁）。"""
    job_id = context.job.id
    assert job_id is not None, "运行中的 job 必然有 job id"
    try:

        logger.info(f"🚀 退出副本 job 开始: job_id={job_id}, user={user_name}")

        game_server = get_runtime_game_server()

        # 获取房间并用每玩家锁避免并发状态竞争
        async with game_server.acquire(user_name) as room:

            # 验证游戏实例类型
            rpg_game = room.game
            if rpg_game is None:
                raise ValueError(f"游戏实例不存在: user={user_name}")
            assert isinstance(rpg_game, DBGGame), "Invalid game type"

            # 退出副本并返回大厅（同步，内部自带状态守卫）
            success, msg = exit_dungeon(rpg_game)
            if not success:
                raise ValueError(f"退出副本失败: {msg}")

            # 销毁副本实体并重置副本数据（同步）
            teardown_dungeon(rpg_game)

            # 存储退出后的世界状态，便于调试和回放
            await store_game_async(rpg_game)

        logger.info(f"✅ 退出副本 job 完成: job_id={job_id}, user={user_name}")

    except Exception as e:
        logger.error(
            f"❌ 退出副本 job 失败: job_id={job_id}, user={user_name}, error={e}"
        )
        raise


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
