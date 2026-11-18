"""游戏局接口：开局、推进、快照。

「局」不是独立路由资源，而是房间里的游戏实例——先 ``POST /api/rooms/v1/{user}``
进入房间，再在这里开局。对局状态本身以快照为准，内存实例只是当前工作副本。
"""

from fastapi import APIRouter, Query, status

from ...game.entities.queries import get_player_actor_name
from ...gameplay.dispatch import defer_room_job
from ...gameplay.jobs import advance_game_job
from ...gameplay.offline import load_or_create_game
from ...gameplay.session_history import SessionEventSink, open_session
from ...pgsql import list_game_snapshots
from ...session.access import require_game, require_room
from ..dependencies import CurrentGameServer
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
    game_server: CurrentGameServer, user_name: str, game_name: str
) -> RoomStateResponse:
    """把一局游戏绑定到房间；已绑定同名游戏时直接返回当前状态（幂等）。"""

    room = require_room(game_server, user_name)
    if room.game is not None and room.game.name == game_name:
        return room_state(room)

    # 会话先就位，游戏才能把领域事件写进历史
    session = room.player_session or open_session(user_name)
    sink = SessionEventSink(session)

    # 读快照/建蓝图都要访问数据库，放在房间锁外，避免阻塞同房间的其他请求
    game = await load_or_create_game(user_name, game_name, events=sink)
    session.set_context(actor=get_player_actor_name(game), game=game_name)

    async with room.transaction():
        room.bind(game=game, player_session=session)

    return room_state(room)


################################################################################################################
@games_api_router.post(
    "/{user_name}/{game_name}/advance",
    response_model=DispatchJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="派发一次 pass（后台 job）",
)
async def advance_game(
    game_server: CurrentGameServer, user_name: str, game_name: str
) -> DispatchJobResponse:
    """派发一次推进，立即返回 job id；执行进度走 ``/api/jobs/v1`` 查询。

    同一房间同时只允许一个 job 排队，重复派发返回 409。
    """

    require_game(game_server, user_name, game_name)
    job_id = await defer_room_job(advance_game_job, user_name=user_name)
    return DispatchJobResponse(job_id=job_id)


################################################################################################################
@games_api_router.get(
    "/{user_name}/{game_name}/snapshots",
    response_model=SnapshotListResponse,
    summary="列出该局的快照元数据（时间倒序）",
)
async def list_snapshots(
    game_server: CurrentGameServer,
    user_name: str,
    game_name: str,
    limit: int = Query(default=20, ge=1, le=200),
) -> SnapshotListResponse:
    """快照是持久化真相：每次 pass 前追加一条，回滚与恢复都以它为准。"""

    require_room(game_server, user_name)
    return SnapshotListResponse(
        snapshots=list_game_snapshots(user_name, game_name, limit=limit)
    )
