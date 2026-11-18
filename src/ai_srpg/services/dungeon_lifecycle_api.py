"""
副本生命周期 API 路由模块（进入、关卡推进、退出等与具体房间类型无关的流程接口）
"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger

from ..game.context import SRPGGame
from ..game.dungeon import (
    current_dungeon_combat,
    current_room_index,
    get_dungeon_room_by_index,
    is_current_room_dungeon_combat,
    is_player_in_dungeon_stage,
    is_player_in_lobby_stage,
)
from ..models import (
    DungeonAdvanceStageRequest,
    DungeonAdvanceStageResponse,
    DungeonExitRequest,
    DungeonExitResponse,
    DungeonStartRequest,
    DungeonStartResponse,
)
from ..session.server import GameServer
from .dungeon_advance_action import (
    advance_dungeon,
)
from .dungeon_enter_action import (
    enter_dungeon,
)
from .dungeon_lifecycle_jobs import (
    execute_exit_dungeon_job,
)
from .dungeon_setup_action import (
    setup_dungeon,
)
from .game_server_dependencies import CurrentGameServer
from .job_dispatch import defer_room_job

###################################################################################################################################################################
dungeon_lifecycle_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
def _validate_dungeon_prerequisites(
    user_name: str,
    game_server: GameServer,
) -> SRPGGame:
    """
    验证副本操作的前置条件
    """

    # 1. 验证房间存在（玩家已登录）
    if not game_server.has_room(user_name):
        logger.error(f"副本操作失败: 玩家 {user_name} 未登录")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    current_room = game_server.get_room(user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    # 2. 验证游戏实例存在
    if current_room.game is None:
        logger.error(f"副本操作失败: 玩家 {user_name} 没有游戏实例")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="游戏实例不存在，请重新登录",
        )

    # 3. 获取并验证游戏实例类型
    srpg_game = current_room.game

    # 4. 验证玩家在副本状态
    if not is_player_in_dungeon_stage(srpg_game):
        logger.error(f"副本操作失败: 玩家 {user_name} 不在副本状态")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能在副本状态下使用",
        )

    return srpg_game


###################################################################################################################################################################
def _validate_dungeon_prerequisites_lobby(
    user_name: str,
    game_server: GameServer,
) -> SRPGGame:
    """验证开始副本的前置条件：房间、游戏实例存在，玩家在大厅且没有进行中的副本。"""
    if not game_server.has_room(user_name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    current_room = game_server.get_room(user_name)
    if current_room is None or current_room.game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="游戏实例不存在，请重新登录",
        )

    srpg_game = current_room.game
    if not is_player_in_lobby_stage(srpg_game):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能在大厅开始副本",
        )
    if current_room_index(srpg_game) >= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前已有进行中的副本",
        )
    return srpg_game


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_lifecycle_api_router.post(
    path="/api/dungeon/progress/advance_stage/v1/",
    response_model=DungeonAdvanceStageResponse,
)
async def dungeon_advance_stage(
    payload: DungeonAdvanceStageRequest,
    game_server: CurrentGameServer,
) -> DungeonAdvanceStageResponse:
    """
    副本关卡推进接口
    """

    logger.info(f"/api/dungeon/progress/advance_stage/v1/: user={payload.user_name}")

    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room.transaction():

        # 验证副本操作的前置条件
        rpg_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        # 若当前为战斗房间，验证战斗是否处于等待阶段（即战斗已结束）
        if is_current_room_dungeon_combat(rpg_game):
            if not current_dungeon_combat(rpg_game).is_post_combat:
                logger.error(
                    f"玩家 {payload.user_name} 前进下一关失败: 战斗未处于等待阶段"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="战斗未处于等待阶段",
                )

            if current_dungeon_combat(rpg_game).is_lost:
                logger.warning(f"玩家 {payload.user_name} 战斗失败")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="战斗失败，无法继续",
                )

            if not current_dungeon_combat(rpg_game).is_won:
                logger.error(f"玩家 {payload.user_name} 战斗状态异常: 既未胜利也未失败")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="战斗状态异常",
                )

        # 获取下一房间索引和房间实例，确保存在下一房间，否则无法推进副本
        next_room_index = current_room_index(rpg_game) + 1
        next_room = get_dungeon_room_by_index(rpg_game, next_room_index)
        if next_room is None:
            logger.error(f"玩家 {payload.user_name} 副本前进失败，没有更多房间")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="副本已全部通关，请返回营地",
            )

        # 推进副本到下一房间
        success, msg = await advance_dungeon(rpg_game)
        if not success:
            logger.error(f"玩家 {payload.user_name} 副本前进失败: {msg}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=msg,
            )

        # 推进副本到下一房间后，返回成功消息
        return DungeonAdvanceStageResponse(message="已前进到下一关")


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_lifecycle_api_router.post(
    path="/api/dungeon/exit/v1/", response_model=DungeonExitResponse
)
async def dungeon_exit(
    payload: DungeonExitRequest,
    game_server: CurrentGameServer,
) -> DungeonExitResponse:
    """
    副本退出接口
    """

    logger.info(f"/api/dungeon/exit/v1/: user={payload.user_name}")

    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    # 验证副本操作的前置条件
    srpg_game = _validate_dungeon_prerequisites(
        user_name=payload.user_name,
        game_server=game_server,
    )

    # 若当前为战斗房间，验证战斗是否已结束
    if is_current_room_dungeon_combat(srpg_game):
        if not current_dungeon_combat(srpg_game).is_post_combat:
            logger.error(f"玩家 {payload.user_name} 返回大厅失败: 战斗未结束")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只能在战斗结束后回家",
            )

    # 派发退出副本 job
    job_id = await defer_room_job(execute_exit_dungeon_job, user_name=payload.user_name)
    logger.info(f"📝 创建 退出副本 job: job_id={job_id}, user={payload.user_name}")

    # 返回退出副本 job 启动成功的响应
    return DungeonExitResponse(
        job_id=job_id,
        message="退出副本 job 已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_lifecycle_api_router.post(
    path="/api/dungeon/start/v1/", response_model=DungeonStartResponse
)
async def dungeon_start(
    payload: DungeonStartRequest,
    game_server: CurrentGameServer,
) -> DungeonStartResponse:
    """
    副本开始接口（从大厅传送至副本第一关）
    """

    logger.info(f"/api/dungeon/start/v1/: user={payload.user_name}")

    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room.transaction():
        # 验证前置条件（玩家必须在大厅，且没有进行中的副本）
        rpg_game = _validate_dungeon_prerequisites_lobby(
            user_name=payload.user_name,
            game_server=game_server,
        )

        # 第一步：从文件加载副本并创建 实体（幂等）
        success, error_detail = setup_dungeon(rpg_game, payload.dungeon_name)
        if not success:
            logger.error(f"玩家 {payload.user_name} 副本实体创建 失败: {error_detail}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="副本实体创建 失败",
            )

        # 第二步：传送玩家并进入第一关
        success, error_detail = enter_dungeon(rpg_game)
        if not success:
            logger.error(f"玩家 {payload.user_name} 进入副本失败: {error_detail}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="进入副本失败",
            )

        # 返回传送成功响应
        return DungeonStartResponse(
            message=f"已进入副本: {payload.dungeon_name}",
        )


###################################################################################################################################################################
###################################################################################################################################################################
