"""房间 / 游戏局路由的 C/S 契约测试。

只验证 HTTP 收发与状态机（进入房间 → 开局 → 派发 → 离开）：开局加载与队列派发
被替换为假实现，这一层不碰数据库与 Procrastinate。
"""

from typing import Any, Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_srpg.game.assembly import create_srpg_game
from ai_srpg.gameplay import session_history
from ai_srpg.gameplay.jobs import advance_game_job
from ai_srpg.models import SessionMessage
from ai_srpg.services.api import games as games_module
from ai_srpg.services.api.games import games_api_router
from ai_srpg.services.api.rooms import rooms_api_router
from ai_srpg.services.http_errors import register_room_error_handlers
from ai_srpg.session.errors import RoomJobBusyError
from ai_srpg.session.registry import RoomRegistry

ROOMS = "/api/rooms/v1"
GAMES = "/api/games/v1"


###############################################################################
class _MemoryStore:
    """内存版会话存储：只记游标，落库留给集成测试。"""

    def __init__(self) -> None:
        self.messages: List[SessionMessage] = []

    def latest_sequence(self, room_id: str) -> int:
        return max((m.sequence_id for m in self.messages), default=0)

    def append(self, room_id: str, message: SessionMessage) -> None:
        self.messages.append(message)

    def messages_since(
        self, room_id: str, after_sequence_id: int, **kwargs: Any
    ) -> List[SessionMessage]:
        return [m for m in self.messages if m.sequence_id > after_sequence_id]


###############################################################################
@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    register_room_error_handlers(app)
    app.include_router(rooms_api_router)
    app.include_router(games_api_router)
    app.state.room_registry = RoomRegistry()
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _memory_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    """会话游标来自存储层；单元测试一律换成内存实现，避免读开发库。"""
    monkeypatch.setattr(session_history, "session_store", _MemoryStore)


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> Dict[str, List[Any]]:
    """替换开局与派发：记录调用参数，避免访问数据库与队列。"""
    recorded: Dict[str, List[Any]] = {"load": [], "defer": []}

    async def fake_load(room_id: str, game_name: str, **kwargs: Any) -> Any:
        recorded["load"].append((room_id, game_name))
        return create_srpg_game(name=game_name)

    async def fake_defer(job_func: Any, *, room_id: str) -> int:
        recorded["defer"].append((job_func, room_id))
        return 42

    monkeypatch.setattr(games_module, "load_or_create_game", fake_load)
    monkeypatch.setattr(games_module, "defer_room_job", fake_defer)
    monkeypatch.setattr(games_module, "list_game_snapshots", lambda *a, **k: [])
    return recorded


###############################################################################
def test_enter_creates_room_and_session(client: TestClient) -> None:
    response = client.post(f"{ROOMS}/alice")

    assert response.status_code == 201
    assert response.json() == {
        "user_name": "alice",
        "room_id": "alice",
        "owner": "alice",
        "game": None,
        "session_event_sequence": 0,
        "seats": [{"user_name": "alice", "actor": None}],
    }


def test_enter_is_idempotent(client: TestClient, app: FastAPI) -> None:
    assert client.post(f"{ROOMS}/alice").status_code == 201

    response = client.post(f"{ROOMS}/alice")

    assert response.status_code == 200
    assert len(app.state.room_registry.snapshot_rooms()) == 1


def test_get_unknown_room_is_404(client: TestClient) -> None:
    response = client.get(f"{ROOMS}/bob")

    assert response.status_code == 404
    assert response.json() == {"detail": "没有房间，请先登录"}


def test_leave_room_closes_it(client: TestClient) -> None:
    client.post(f"{ROOMS}/alice")

    assert client.delete(f"{ROOMS}/alice").status_code == 204
    assert client.get(f"{ROOMS}/alice").status_code == 404


def test_leave_unknown_room_is_404(client: TestClient) -> None:
    assert client.delete(f"{ROOMS}/ghost").status_code == 404


###############################################################################
def test_open_game_binds_game_to_room(
    client: TestClient, calls: Dict[str, List[Any]]
) -> None:
    client.post(f"{ROOMS}/alice")

    response = client.post(f"{GAMES}/alice/Game1")

    assert response.status_code == 200
    assert response.json()["game"] == "Game1"
    assert calls["load"] == [("alice", "Game1")]


def test_open_game_is_idempotent(
    client: TestClient, calls: Dict[str, List[Any]]
) -> None:
    client.post(f"{ROOMS}/alice")
    client.post(f"{GAMES}/alice/Game1")

    client.post(f"{GAMES}/alice/Game1")

    assert len(calls["load"]) == 1


def test_open_game_requires_room(
    client: TestClient, calls: Dict[str, List[Any]]
) -> None:
    response = client.post(f"{GAMES}/ghost/Game1")

    assert response.status_code == 404
    assert calls["load"] == []


def test_open_game_does_not_need_room_lock_while_loading(
    client: TestClient, app: FastAPI, calls: Dict[str, List[Any]]
) -> None:
    """开局加载在锁外进行：加载期间房间不忙，其他请求仍可进入。"""
    client.post(f"{ROOMS}/alice")

    client.post(f"{GAMES}/alice/Game1")

    room = app.state.room_registry.get_room("alice")
    assert room is not None
    assert not room.is_busy


###############################################################################
def test_advance_dispatches_job(
    client: TestClient, calls: Dict[str, List[Any]]
) -> None:
    client.post(f"{ROOMS}/alice")
    client.post(f"{GAMES}/alice/Game1")

    response = client.post(f"{GAMES}/alice/Game1/advance")

    assert response.status_code == 202
    assert response.json() == {"job_id": 42}
    assert calls["defer"] == [(advance_game_job, "alice")]


def test_advance_without_game_is_404(
    client: TestClient, calls: Dict[str, List[Any]]
) -> None:
    client.post(f"{ROOMS}/alice")

    response = client.post(f"{GAMES}/alice/Game1/advance")

    assert response.status_code == 404
    assert response.json() == {"detail": "没有游戏，请先登录"}
    assert calls["defer"] == []


def test_advance_with_wrong_game_name_is_400(
    client: TestClient, calls: Dict[str, List[Any]]
) -> None:
    client.post(f"{ROOMS}/alice")
    client.post(f"{GAMES}/alice/Game1")

    response = client.post(f"{GAMES}/alice/Game2/advance")

    assert response.status_code == 400
    assert response.json() == {"detail": "游戏名称不匹配"}


def test_advance_returns_409_when_room_job_busy(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    calls: Dict[str, List[Any]],
) -> None:
    client.post(f"{ROOMS}/alice")
    client.post(f"{GAMES}/alice/Game1")

    async def busy(job_func: Any, *, room_id: str) -> int:
        raise RoomJobBusyError(room_id)

    monkeypatch.setattr(games_module, "defer_room_job", busy)

    response = client.post(f"{GAMES}/alice/Game1/advance")

    assert response.status_code == 409


###############################################################################
def test_snapshots_returns_list(
    client: TestClient, calls: Dict[str, List[Any]]
) -> None:
    client.post(f"{ROOMS}/alice")

    response = client.get(f"{GAMES}/alice/Game1/snapshots")

    assert response.status_code == 200
    assert response.json() == {"snapshots": []}


def test_snapshots_requires_room(
    client: TestClient, calls: Dict[str, List[Any]]
) -> None:
    assert client.get(f"{GAMES}/ghost/Game1/snapshots").status_code == 404


###############################################################################
def test_openapi_documents_cs_surface(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]

    assert "/api/rooms/v1/{user_name}" in paths
    assert "/api/games/v1/{user_name}/{game_name}" in paths
    assert "/api/games/v1/{user_name}/{game_name}/advance" in paths
    assert paths["/api/rooms/v1/{user_name}"]["post"]["tags"] == ["rooms"]
    assert paths["/api/games/v1/{user_name}/{game_name}/advance"]["post"]["tags"] == [
        "games"
    ]
