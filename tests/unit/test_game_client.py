"""客户端契约测试：URL 构造、响应解析、错误映射与轮询语义。

不启动服务器，用 ``httpx.MockTransport`` 直接喂响应；服务端契约由
``services.api.schemas`` 共用，因此这里也顺带验证「客户端按同一定义解析」。
"""

from typing import Any, Callable, List

import httpx
import pytest
from procrastinate.jobs import Status as JobStatus

from ai_srpg.srpg_game_client.core import GameClient, GameClientError, JobWaitTimeout

Handler = Callable[[httpx.Request], httpx.Response]


###############################################################################
def _client(handler: Handler) -> GameClient:
    return GameClient("http://testserver", transport=httpx.MockTransport(handler))


def _state(user_name: str, game: str | None = None) -> dict[str, Any]:
    return {
        "user_name": user_name,
        "room_id": user_name,
        "owner": user_name,
        "game": game,
        "session_event_sequence": 0,
        "seats": [{"user_name": user_name, "actor": None}],
    }


def _job(job_id: int, status: JobStatus) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "status": status.value,
        "error": None,
        "events": [],
    }


###############################################################################
def test_enter_room_escapes_path_and_parses_response() -> None:
    seen: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(201, json=_state("角色.无名"))

    with _client(handler) as client:
        state = client.enter_room("角色.无名")

    assert seen[0].method == "POST"
    assert "%E8%A7%92%E8%89%B2" in str(seen[0].url)
    assert state.user_name == "角色.无名"
    assert state.game is None


def test_leave_room_accepts_empty_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        return httpx.Response(204)

    with _client(handler) as client:
        client.leave_room("alice")


def test_open_game_and_advance() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/advance"):
            assert request.method == "POST"
            return httpx.Response(202, json={"job_id": 7})
        return httpx.Response(200, json=_state("alice", "Game1"))

    with _client(handler) as client:
        state = client.open_game("alice", "Game1")
        job_id = client.advance("alice", "Game1")

    assert state.game == "Game1"
    assert job_id == 7


def test_snapshots_and_messages_pass_query_params() -> None:
    seen: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/snapshots"):
            return httpx.Response(200, json={"snapshots": []})
        return httpx.Response(200, json={"session_messages": []})

    with _client(handler) as client:
        assert client.snapshots("alice", "Game1", limit=5) == []
        assert client.session_messages("alice", since=3) == []

    assert dict(seen[0].url.params) == {"limit": "5"}
    assert dict(seen[1].url.params) == {"last_sequence_id": "3"}


###############################################################################
def test_error_detail_is_parsed_into_client_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "没有房间，请先登录"})

    with _client(handler) as client:
        with pytest.raises(GameClientError) as excinfo:
            client.room_state("bob")

    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "没有房间，请先登录"


def test_error_without_json_falls_back_to_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    with _client(handler) as client:
        with pytest.raises(GameClientError) as excinfo:
            client.room_state("bob")

    assert excinfo.value.status_code == 500
    assert excinfo.value.detail == "boom"


###############################################################################
def test_wait_job_polls_until_terminal() -> None:
    responses = [
        _job(1, JobStatus.TODO),
        _job(1, JobStatus.DOING),
        _job(1, JobStatus.SUCCEEDED),
    ]
    seen: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=responses.pop(0))

    with _client(handler) as client:
        detail = client.wait_job(1, timeout=5.0, interval=0.0)

    assert detail.status == JobStatus.SUCCEEDED
    assert len(seen) == 3


def test_wait_job_times_out_without_claiming_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_job(1, JobStatus.DOING))

    with _client(handler) as client:
        with pytest.raises(JobWaitTimeout) as excinfo:
            client.wait_job(1, timeout=0.05, interval=0.01)

    assert excinfo.value.job_id == 1
