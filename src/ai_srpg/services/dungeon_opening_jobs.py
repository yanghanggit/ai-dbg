"""
副本开场房间 job 模块：开场初始化（叙事 + 环境初始化，无战斗）。
"""

from loguru import logger
from procrastinate import JobContext

from ..game.context import SRPGGame
from ..game.dungeon import (
    is_current_room_dungeon_opening,
)
from ..game.pipelines import process_pipeline
from ..job_context import get_current_job
from ..pgsql import procrastinate_app
from .game_server_runtime import get_runtime_game_server
from .job_runtime import job_task


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
@job_task(action="opening_room_init")
async def execute_opening_room_init_job(
    context: JobContext,
    user_name: str,
) -> None:
    """执行副本开场房间初始化 job（叙事 + 环境初始化，无战斗）"""
    job_id = context.job.id
    assert job_id is not None, "运行中的 job 必然有 job id"
    try:

        logger.info(f"🚀 开场房间初始化 job 开始: job_id={job_id}, user={user_name}")

        game_server = get_runtime_game_server()

        # 获取房间并用每玩家锁避免并发状态竞争
        async with game_server.acquire(user_name) as room:

            # 验证游戏实例类型
            rpg_game = room.game
            if rpg_game is None:
                raise ValueError(f"游戏实例不存在: user={user_name}")
            assert isinstance(rpg_game, SRPGGame), "Invalid game type"

            # 验证当前副本房间是否为开场房间
            if not is_current_room_dungeon_opening(rpg_game):
                raise ValueError("当前副本房间不是开场房间")

            # 推进开场房间流程（叙事 + 牌库初始化，无战斗）
            await process_pipeline(rpg_game.pipeline, get_current_job())

            # 存储开场房间初始化后的世界状态，便于调试和回放

        logger.info(f"✅ 开场房间初始化 job 完成: job_id={job_id}, user={user_name}")

    except Exception as e:
        logger.error(
            f"❌ 开场房间初始化 job 失败: job_id={job_id}, user={user_name}, error={e}"
        )
        raise


###################################################################################################################################################################
###################################################################################################################################################################
