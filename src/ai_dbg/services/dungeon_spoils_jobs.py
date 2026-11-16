"""
副本奖励（Spoils）job 模块：生成候选奖励 / 领取卡牌。
"""

from loguru import logger
from procrastinate import JobContext

from ..game.context import DBGGame
from ..game.dungeon import (
    is_current_room_dungeon_combat,
)
from ..game.persistence.store import store_game_async
from ..job_context import get_current_job
from ..pgsql import procrastinate_app
from .dungeon_spoils_actions import (
    activate_generate_spoils,
    activate_pick_spoils_card,
    party_has_any_spoils,
)
from .game_server_runtime import get_runtime_game_server
from .job_runtime import job_task


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
@job_task(action="generate_spoils")
async def execute_generate_spoils_job(
    context: JobContext,
    user_name: str,
) -> None:
    """执行奖励生成 job（外部触发 GenerateSpoilsAction 后推动全局 pipeline 处理）"""
    job_id = context.job.id
    assert job_id is not None, "运行中的 job 必然有 job id"
    try:
        logger.info(f"🚀 奖励生成 job 开始: job_id={job_id}, user={user_name}")

        game_server = get_runtime_game_server()

        # 获取房间并用每玩家锁避免并发状态竞争
        async with game_server.acquire(user_name) as room:
            # 验证游戏实例类型
            rpg_game = room.game
            if rpg_game is None:
                raise ValueError(f"游戏实例不存在: user={user_name}")
            assert isinstance(rpg_game, DBGGame), "Invalid game type"

            # 验证当前副本房间为非战斗房间
            if is_current_room_dungeon_combat(rpg_game):
                raise ValueError("当前副本房间是战斗房间")

            # 外部显式激活奖励生成动作（内部含幂等守卫）
            success, message = activate_generate_spoils(rpg_game)
            if not success:
                raise ValueError(f"奖励生成失败: {message}")

            # 推进开场房间流程，让 GenerateSpoilsActionSystem 响应并生成奖励
            await rpg_game.pipeline.process(get_current_job())

            # 零产出即失败：设计会话出错时不会写入 SpoilsComponent（出错就没有结果）。
            # 这里显式报错，外部才能区分「发奖成功」与「什么都没发」，而不是静默返回。
            if not party_has_any_spoils(rpg_game):
                raise ValueError("奖励生成未完成，可重试")

            # 存储奖励生成后的世界状态，便于调试和回放
            await store_game_async(rpg_game)

        logger.info(f"✅ 奖励生成 job 完成: job_id={job_id}, user={user_name}")

    except Exception as e:
        logger.error(
            f"❌ 奖励生成 job 失败: job_id={job_id}, user={user_name}, error={e}"
        )
        raise


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
@job_task(action="pick_spoils_card")
async def execute_pick_spoils_card_job(
    context: JobContext,
    user_name: str,
    actor_name: str,
    card_name: str,
) -> None:
    """执行从 Spoils 领取一张卡牌 job（外部触发 PickSpoilsAction 后推动全局 pipeline 处理）"""
    job_id = context.job.id
    assert job_id is not None, "运行中的 job 必然有 job id"
    try:
        logger.info(
            f"🚀 领卡 job 开始: job_id={job_id}, user={user_name}, actor={actor_name}, card={card_name}"
        )

        game_server = get_runtime_game_server()

        # 获取房间并用每玩家锁避免并发状态竞争
        async with game_server.acquire(user_name) as room:
            # 验证游戏实例类型
            rpg_game = room.game
            if rpg_game is None:
                raise ValueError(f"游戏实例不存在: user={user_name}")
            assert isinstance(rpg_game, DBGGame), "Invalid game type"

            # 验证当前副本房间为非战斗房间
            if is_current_room_dungeon_combat(rpg_game):
                raise ValueError("当前副本房间是战斗房间")

            # 外部显式激活领卡动作（内部含 Spoils 存在 + 卡牌检索守卫）
            success, message = activate_pick_spoils_card(
                rpg_game, actor_name, card_name
            )
            if not success:
                raise ValueError(f"从 Spoils 领卡失败: {message}")

            # 推进开场房间流程，让 PickSpoilsActionSystem 响应并把选中卡加入牌库
            await rpg_game.pipeline.process(get_current_job())

            # 存储领卡后的世界状态，便于调试和回放
            await store_game_async(rpg_game)

        logger.info(f"✅ 领卡 job 完成: job_id={job_id}, user={user_name}")

    except Exception as e:
        logger.error(f"❌ 领卡 job 失败: job_id={job_id}, user={user_name}, error={e}")
        raise


###################################################################################################################################################################
###################################################################################################################################################################
