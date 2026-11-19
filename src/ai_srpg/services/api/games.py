"""游戏局接口：开局、推进、快照；状态以快照为准，内存实例只是工作副本。"""

from fastapi import APIRouter, Query, status

from ...game.entities.queries import get_player_actor_name
from ...gameplay.dispatch import defer_room_job
from ...gameplay.jobs import advance_game_job
from ...gameplay.offline import load_or_create_game
from ...gameplay.session_history import SessionEventSink, open_session
from ...pgsql import list_game_snapshots
from ...session.access import require_room_of_user, require_room_with_game
from ..dependencies import CurrentRoomRegistry
from .rooms import room_state
from .schemas import DispatchJobResponse, RoomStateResponse, SnapshotListResponse

################################################################################################################
games_api_router = APIRouter(prefix="/api/games/v1", tags=["games"])


################################################################################################################
@games_api_router.post(
    "/{user_name}/{game_name}",
    response_model=RoomStateResponse,
    summary="开局：加载最新快照，没有快照则从蓝图新建",
)
async def open_game(
    room_registry: CurrentRoomRegistry, user_name: str, game_name: str
) -> RoomStateResponse:
    """把一局游戏绑定到房间；已绑定同名游戏时直接返回当前状态（幂等）。"""

    room = require_room_of_user(room_registry, user_name)
    if room.game is not None and room.game.name == game_name:
        return room_state(room, user_name)

    # 会话先就位，游戏才能把领域事件写进局级历史流
    session = room.session_of(user_name) or open_session(room.room_id, user_name)
    sink = SessionEventSink(room, session)

    # 读快照/建蓝图都要访问数据库，放在房间锁外，避免阻塞同房间的其他请求
    game = await load_or_create_game(
        room.room_id, game_name, user_name=user_name, events=sink
    )
    actor = get_player_actor_name(game)
    session.set_context(actor=actor, game=game_name)

    async with room.transaction():
        room.attach_session(session)
        room.start_game(game=game)
        if actor is not None:
            room.bind_seat_actor(user_name, actor)

    return room_state(room, user_name)


################################################################################################################
@games_api_router.post(
    "/{user_name}/{game_name}/advance",
    response_model=DispatchJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="派发一次 pass（后台 job）",
)
async def advance_game(
    room_registry: CurrentRoomRegistry, user_name: str, game_name: str
) -> DispatchJobResponse:
    """派发一次推进并返回 job id；同一房间只允许一个 job 排队（重复派发 409）。"""

    room = require_room_with_game(room_registry, user_name, game_name)
    job_id = await defer_room_job(advance_game_job, room_id=room.room_id)
    return DispatchJobResponse(job_id=job_id)


################################################################################################################
@games_api_router.get(
    "/{user_name}/{game_name}/snapshots",
    response_model=SnapshotListResponse,
    summary="列出该局的快照元数据（时间倒序）",
)
async def list_snapshots(
    room_registry: CurrentRoomRegistry,
    user_name: str,
    game_name: str,
    limit: int = Query(default=20, ge=1, le=200),
) -> SnapshotListResponse:
    """快照是持久化真相：每次 pass 前追加一条，回滚与恢复都以它为准。"""

    room = require_room_of_user(room_registry, user_name)
    return SnapshotListResponse(
        snapshots=list_game_snapshots(room.room_id, game_name, limit=limit)
    )
