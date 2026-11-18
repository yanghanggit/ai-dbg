"""
副本战斗 job 模块
"""

from typing import List

from loguru import logger
from procrastinate import JobContext

from ..game.context import SRPGGame
from ..game.dungeon import (
    current_dungeon_combat,
    is_current_room_dungeon_combat,
)
from ..game.entities import (
    get_actor_entity,
)
from ..game.persistence.store import store_game_async
from ..game.pipelines import process_pipeline
from ..job_context import get_current_job
from ..models import MonsterComponent
from ..pgsql import procrastinate_app
from .dungeon_combat_actions import (
    activate_all_card_draws,
    activate_equip_gear,
    activate_monster_play_trigger,
    activate_pass_turn,
    activate_play_cards_specified,
    activate_retreat,
    activate_use_consumable,
)
from .game_server_runtime import get_runtime_game_server
from .job_runtime import job_task


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
@job_task(action="init_combat")
async def execute_init_combat_job(
    context: JobContext,
    user_name: str,
) -> None:
    """执行战斗初始化 job"""
    job_id = context.job.id
    assert job_id is not None, "运行中的 job 必然有 job id"
    try:

        logger.info(f"🚀 战斗初始化 job 开始: job_id={job_id}, user={user_name}")

        game_server = get_runtime_game_server()

        # 获取房间并用每玩家锁避免并发状态竞争
        async with game_server.acquire(user_name) as room:

            # 验证游戏实例类型
            rpg_game = room.game
            if rpg_game is None:
                raise ValueError(f"游戏实例不存在: user={user_name}")
            assert isinstance(rpg_game, SRPGGame), "Invalid game type"

            # 验证当前副本房间是否为战斗房间
            if not is_current_room_dungeon_combat(rpg_game):
                raise ValueError("当前副本房间不是战斗房间")

            # 验证战斗状态
            if not current_dungeon_combat(rpg_game).is_initializing:
                raise ValueError("战斗未处于开始阶段")

            # 推进战斗流程处理战斗初始化
            await process_pipeline(rpg_game.pipeline, get_current_job())

            # 存储战斗初始化后的世界状态，便于调试和回放
            await store_game_async(rpg_game)

        logger.info(f"✅ 战斗初始化 job 完成: job_id={job_id}, user={user_name}")

    except Exception as e:
        logger.error(
            f"❌ 战斗初始化 job 失败: job_id={job_id}, user={user_name}, error={e}"
        )
        raise


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
@job_task(action="retreat")
async def execute_retreat_job(
    context: JobContext,
    user_name: str,
) -> None:
    """执行撤退 job"""
    job_id = context.job.id
    assert job_id is not None, "运行中的 job 必然有 job id"
    try:

        logger.info(f"🚀 撤退 job 开始: job_id={job_id}, user={user_name}")

        game_server = get_runtime_game_server()

        # 获取房间并用每玩家锁避免并发状态竞争
        async with game_server.acquire(user_name) as room:

            # 验证战斗状态
            rpg_game = room.game
            if rpg_game is None:
                raise ValueError(f"游戏实例不存在: user={user_name}")
            assert isinstance(rpg_game, SRPGGame), "Invalid game type"

            # 验证当前副本房间是否为战斗房间
            if not is_current_room_dungeon_combat(rpg_game):
                raise ValueError("当前副本房间不是战斗房间")

            # 激活撤退动作
            success, message = activate_retreat(rpg_game)
            if not success:
                raise ValueError(message)

            # 执行战斗流程让 CombatOutcomeSystem 检测到角色死亡并判定失败
            await process_pipeline(rpg_game.pipeline, get_current_job())

            # 确认已进入 post_combat 状态
            if not current_dungeon_combat(rpg_game).is_post_combat:
                raise RuntimeError(
                    "全局 pipeline 执行后未进入 post_combat 状态，撤退流程异常"
                )

            # 存储撤退后进入 post_combat 状态的世界状态，便于调试和回放
            await store_game_async(rpg_game)

        logger.info(
            f"✅ 撤退 job 完成: job_id={job_id}, user={user_name}, 战斗已标记为失败。请调用 /api/dungeon/exit/v1/ 返回大厅。"
        )

    except Exception as e:
        logger.error(f"❌ 撤退 job 失败: job_id={job_id}, user={user_name}, error={e}")
        raise


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
@job_task(action="draw_cards")
async def execute_draw_cards_job(
    context: JobContext,
    user_name: str,
) -> None:
    """执行抽卡 job"""
    job_id = context.job.id
    assert job_id is not None, "运行中的 job 必然有 job id"
    try:

        logger.info(f"🚀 抽卡 job 开始: job_id={job_id}, user={user_name}")

        game_server = get_runtime_game_server()

        # 获取房间并用每玩家锁避免并发状态竞争
        async with game_server.acquire(user_name) as room:

            # 验证游戏实例类型
            rpg_game = room.game
            if rpg_game is None:
                raise ValueError(f"游戏实例不存在: user={user_name}")
            assert isinstance(rpg_game, SRPGGame), "Invalid game type"

            # 验证当前副本房间是否为战斗房间
            if not is_current_room_dungeon_combat(rpg_game):
                raise ValueError("当前副本房间不是战斗房间")

            # 验证战斗状态
            if not current_dungeon_combat(rpg_game).is_ongoing:
                raise ValueError("战斗未在进行中")

            # 激活全员抽牌动作
            success, message = activate_all_card_draws(rpg_game)
            if not success:
                raise ValueError(message)

            # 推进战斗流程处理抽牌
            await process_pipeline(rpg_game.pipeline, get_current_job())

            # 存储抽牌后的世界状态，便于调试和回放
            await store_game_async(rpg_game)

        logger.info(f"✅ 抽卡 job 完成: job_id={job_id}, user={user_name}")

    except Exception as e:
        logger.error(f"❌ 抽卡 job 失败: job_id={job_id}, user={user_name}, error={e}")
        raise


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
@job_task(action="play_cards")
async def execute_play_cards_job(
    context: JobContext,
    user_name: str,
    actor_name: str,
    card_name: str,
    targets: List[str],
) -> None:
    """执行出牌 job"""
    job_id = context.job.id
    assert job_id is not None, "运行中的 job 必然有 job id"
    try:
        logger.info(f"🚀 出牌 job 开始: job_id={job_id}, user={user_name}")

        game_server = get_runtime_game_server()

        # 获取房间并用每玩家锁避免并发状态竞争
        async with game_server.acquire(user_name) as room:

            # 验证游戏实例类型
            rpg_game = room.game
            if rpg_game is None:
                raise ValueError(f"游戏实例不存在: user={user_name}")
            assert isinstance(rpg_game, SRPGGame), "Invalid game type"

            # 验证当前副本房间是否为战斗房间
            if not is_current_room_dungeon_combat(rpg_game):
                raise ValueError("当前副本房间不是战斗房间")

            # 验证战斗状态
            if not current_dungeon_combat(rpg_game).is_ongoing:
                raise ValueError("战斗未在进行中")

            # 激活出牌动作（怪物由 MonsterCombatDecisionSystem 自动决策，玩家按指定卡牌出牌）
            actor_entity = get_actor_entity(rpg_game, actor_name)
            if actor_entity is not None and actor_entity.has(MonsterComponent):
                success, message = activate_monster_play_trigger(rpg_game, actor_name)
            else:
                success, message = await activate_play_cards_specified(
                    rpg_game, actor_name, card_name, targets
                )
            if not success:
                raise ValueError(message)

            # 推进战斗流程处理出牌
            await process_pipeline(rpg_game.pipeline, get_current_job())

            # 存储出牌后的世界状态，便于调试和回放
            await store_game_async(rpg_game)

        logger.info(f"✅ 出牌 job 完成: job_id={job_id}, user={user_name}")

    except Exception as e:
        logger.error(f"❌ 出牌 job 失败: job_id={job_id}, user={user_name}, error={e}")
        raise


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
@job_task(action="pass_turn")
async def execute_pass_turn_job(
    context: JobContext,
    user_name: str,
    actor_name: str,
) -> None:
    """执行过牌 job"""
    job_id = context.job.id
    assert job_id is not None, "运行中的 job 必然有 job id"
    try:
        logger.info(f"🚀 过牌 job 开始: job_id={job_id}, user={user_name}")

        game_server = get_runtime_game_server()

        # 获取房间并用每玩家锁避免并发状态竞争
        async with game_server.acquire(user_name) as room:

            # 验证游戏实例类型
            rpg_game = room.game
            if rpg_game is None:
                raise ValueError(f"游戏实例不存在: user={user_name}")
            assert isinstance(rpg_game, SRPGGame), "Invalid game type"

            # 验证当前副本房间是否为战斗房间
            if not is_current_room_dungeon_combat(rpg_game):
                raise ValueError("当前副本房间不是战斗房间")

            # 验证战斗状态
            if not current_dungeon_combat(rpg_game).is_ongoing:
                raise ValueError("战斗未在进行中")

            # 激活过牌动作
            success, message = activate_pass_turn(rpg_game, actor_name)
            if not success:
                raise ValueError(message)

            # 处理战斗流水线
            await process_pipeline(rpg_game.pipeline, get_current_job())

            # 存储过牌后的世界状态，便于调试和回放
            await store_game_async(rpg_game)

        logger.info(f"✅ 过牌 job 完成: job_id={job_id}, user={user_name}")

    except Exception as e:
        logger.error(f"❌ 过牌 job 失败: job_id={job_id}, user={user_name}, error={e}")
        raise


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
@job_task(action="use_consumable")
async def execute_use_consumable_job(
    context: JobContext,
    user_name: str,
    item_name: str,
) -> None:
    """执行使用消耗品 job"""
    job_id = context.job.id
    assert job_id is not None, "运行中的 job 必然有 job id"
    try:

        logger.info(f"🚀 使用消耗品 job 开始: job_id={job_id}, user={user_name}")

        game_server = get_runtime_game_server()

        # 获取房间并用每玩家锁避免并发状态竞争
        async with game_server.acquire(user_name) as room:

            # 验证游戏实例类型
            rpg_game = room.game
            if rpg_game is None:
                raise ValueError(f"游戏实例不存在: user={user_name}")
            assert isinstance(rpg_game, SRPGGame), "Invalid game type"

            # 验证当前副本房间是否为战斗房间
            if not is_current_room_dungeon_combat(rpg_game):
                raise ValueError("当前副本房间不是战斗房间")

            # 验证战斗状态
            if not current_dungeon_combat(rpg_game).is_ongoing:
                raise ValueError("战斗未在进行中")

            # 激活使用消耗品动作
            success, message = activate_use_consumable(rpg_game, item_name)
            if not success:
                raise ValueError(message)

            # 处理战斗流水线
            await process_pipeline(rpg_game.pipeline, get_current_job())

            # 存储使用消耗品后的世界状态，便于调试和回放
            await store_game_async(rpg_game)

        logger.info(f"✅ 使用消耗品 job 完成: job_id={job_id}, user={user_name}")

    except Exception as e:
        logger.error(
            f"❌ 使用消耗品 job 失败: job_id={job_id}, user={user_name}, error={e}"
        )
        raise


###################################################################################################################################################################
###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
@job_task(action="equip_gear")
async def execute_equip_gear_job(
    context: JobContext,
    user_name: str,
    item_name: str,
) -> None:
    """执行使用装备 job"""
    job_id = context.job.id
    assert job_id is not None, "运行中的 job 必然有 job id"
    try:

        logger.info(f"🚀 使用装备 job 开始: job_id={job_id}, user={user_name}")

        game_server = get_runtime_game_server()

        # 获取房间并用每玩家锁避免并发状态竞争
        async with game_server.acquire(user_name) as room:

            # 验证游戏实例类型
            rpg_game = room.game
            if rpg_game is None:
                raise ValueError(f"游戏实例不存在: user={user_name}")
            assert isinstance(rpg_game, SRPGGame), "Invalid game type"

            # 只发起请求；房间、回合、当前行动者、背包与装备查找由 ECS system 处理
            success, message = activate_equip_gear(rpg_game, item_name)
            if not success:
                raise ValueError(message)

            # 处理战斗流水线
            await process_pipeline(rpg_game.pipeline, get_current_job())

            # 存储使用装备后的世界状态，便于调试和回放
            await store_game_async(rpg_game)

        logger.info(f"✅ 使用装备 job 完成: job_id={job_id}, user={user_name}")

    except Exception as e:
        logger.error(
            f"❌ 使用装备 job 失败: job_id={job_id}, user={user_name}, error={e}"
        )
        raise


###################################################################################################################################################################
###################################################################################################################################################################
