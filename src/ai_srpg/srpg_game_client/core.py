"""远程动作层：把服务端 HTTP 接口包成客户端对象。

与 ``srpg_game_agent``（离线、进程内直接读写快照）平级：这里不碰数据库、不碰
队列，只按 OpenAPI 契约收发 JSON，因此适合做端到端验证与远程驱动。

契约（请求/响应模型）与路由共用 ``services.api.schemas``，客户端不再复制一份。
"""

import time
from typing import Any, Final, List, Optional
from urllib.parse import quote

import httpx
from procrastinate.jobs import Status as JobStatus

from ..models import GameSnapshotInfo, SessionMessage
from ..services.api.schemas import (
    JobDetail,
    RoomStateResponse,
    ServerInfoResponse,
    SessionMessageResponse,
    SnapshotListResponse,
)

#: job 的终态集合：到达后状态不再变化（与服务端 jobs 路由的判据一致）
TERMINAL_JOB_STATUSES: Final[frozenset[JobStatus]] = frozenset(
    {
        JobStatus.SUCCEEDED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
        JobStatus.ABORTED,
    }
)


###############################################################################
class GameClientError(RuntimeError):
    """服务端返回 4xx/5xx。"""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"HTTP {status_code}: {detail}")
        self.status_code: int = status_code
        self.detail: str = detail


###############################################################################
class JobWaitTimeout(RuntimeError):
    """等待 job 终态超时（job 仍在执行，不代表失败）。"""

    def __init__(self, job_id: int, timeout: float) -> None:
        super().__init__(f"job {job_id} 在 {timeout:g}s 内未到达终态")
        self.job_id: int = job_id


###############################################################################
def _segment(value: str) -> str:
    """路径段转义：用户名/游戏名可能含中文与点号。"""
    return quote(value, safe="")


###############################################################################
def _error_detail(response: httpx.Response) -> str:
    """取错误响应里的 detail；不是 JSON 时退回原文。"""
    try:
        payload = response.json()
    except ValueError:
        return response.text or response.reason_phrase
    if isinstance(payload, dict) and "detail" in payload:
        return str(payload["detail"])
    return response.text


###############################################################################
class GameClient:
    """游戏服务器的同步 HTTP 客户端。

    一个实例复用一条连接；作为上下文管理器使用时退出即关闭。
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
        )

    ###########################################################################
    @property
    def base_url(self) -> str:
        return str(self._http.base_url)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "GameClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    ###########################################################################
    def _json(self, method: str, url: str, **kwargs: Any) -> Any:
        response = self._http.request(method, url, **kwargs)
        if response.status_code >= 400:
            raise GameClientError(response.status_code, _error_detail(response))
        if not response.content:
            return None
        return response.json()

    ###########################################################################
    # 服务自描述
    ###########################################################################
    def server_info(self) -> ServerInfoResponse:
        """``GET /``：标题、版本与已注册路由清单。"""
        return ServerInfoResponse.model_validate(self._json("GET", "/"))

    ###########################################################################
    # 房间
    ###########################################################################
    def enter_room(self, user_name: str) -> RoomStateResponse:
        """进入房间（=登录）；不存在则创建，已存在则复用。"""
        return RoomStateResponse.model_validate(
            self._json("POST", f"/api/rooms/v1/{_segment(user_name)}")
        )

    def room_state(self, user_name: str) -> RoomStateResponse:
        """查询房间状态；未进入房间时会抛 ``GameClientError``（404）。"""
        return RoomStateResponse.model_validate(
            self._json("GET", f"/api/rooms/v1/{_segment(user_name)}")
        )

    def leave_room(self, user_name: str) -> None:
        """离开房间（关闭并移除内存态，已落库的快照保留）。"""
        self._json("DELETE", f"/api/rooms/v1/{_segment(user_name)}")

    ###########################################################################
    # 游戏
    ###########################################################################
    def open_game(self, user_name: str, game_name: str) -> RoomStateResponse:
        """开局：加载最新快照，没有快照则从蓝图新建；幂等。"""
        return RoomStateResponse.model_validate(
            self._json(
                "POST",
                f"/api/games/v1/{_segment(user_name)}/{_segment(game_name)}",
            )
        )

    def advance(self, user_name: str, game_name: str) -> int:
        """派发一次 pass，返回 job id（执行在服务端后台进行）。"""
        payload = self._json(
            "POST",
            f"/api/games/v1/{_segment(user_name)}/{_segment(game_name)}/advance",
        )
        return int(payload["job_id"])

    def snapshots(
        self, user_name: str, game_name: str, *, limit: int = 20
    ) -> List[GameSnapshotInfo]:
        """该局的快照元数据（时间倒序）。"""
        payload = self._json(
            "GET",
            f"/api/games/v1/{_segment(user_name)}/{_segment(game_name)}/snapshots",
            params={"limit": limit},
        )
        return list(SnapshotListResponse.model_validate(payload).snapshots)

    ###########################################################################
    # 会话历史
    ###########################################################################
    def session_messages(
        self, user_name: str, *, since: int = 0
    ) -> List[SessionMessage]:
        """增量读取用户级会话历史（``since`` 是上一次的最大序号）。"""
        payload = self._json(
            "GET",
            f"/api/session_messages/v1/{_segment(user_name)}/since",
            params={"last_sequence_id": since},
        )
        return list(SessionMessageResponse.model_validate(payload).session_messages)

    ###########################################################################
    # job
    ###########################################################################
    def job(self, job_id: int) -> JobDetail:
        """查询单个 job 的状态与全部执行事件。"""
        return JobDetail.model_validate(self._json("GET", f"/api/jobs/v1/{job_id}"))

    def wait_job(
        self, job_id: int, *, timeout: float = 120.0, interval: float = 0.3
    ) -> JobDetail:
        """轮询直到 job 到达终态；超时抛 ``JobWaitTimeout``（job 可能仍在跑）。"""
        deadline = time.monotonic() + timeout
        while True:
            detail = self.job(job_id)
            if detail.status in TERMINAL_JOB_STATUSES:
                return detail
            if time.monotonic() >= deadline:
                raise JobWaitTimeout(job_id, timeout)
            time.sleep(interval)
