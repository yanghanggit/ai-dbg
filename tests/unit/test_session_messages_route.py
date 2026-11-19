"""会话历史路由测试：只验证契约与参数透传，不访问数据库。"""

from typing import Any, Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_srpg.gameplay import session_history
from ai_srpg.models import NoneEvent, SessionMessage
from ai_srpg.services.api.session_messages import session_messages_api_router
from ai_srpg.session.registry import RoomRegistry

PATH = "/api/session_messages/v1/{user_name}/since"


###############################################################################
class _FakeStore:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def latest_sequence(self, room_id: str) -> int:
        return 0

    def append(self, room_id: str, message: SessionMessage) -> None:
        return None

    def messages_since(
        self,
        room_id: str,
        after_sequence_id: int,
        *,
        viewer: str | None = None,
        limit: int = 500,
    ) -> List[SessionMessage]:
        self.calls.append(
            {
                "room_id": room_id,
                "viewer": viewer,
                "after": after_sequence_id,
                "limit": limit,
            }
        )
        return [
            SessionMessage(
                sequence_id=after_sequence_id + 1,
                agent_event=NoneEvent(message="hi"),
                game_name="Game1",
            )
        ]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app = FastAPI()
    app.state.room_registry = RoomRegistry()  # 没有房间：路由回退用用户名当局号
    app.include_router(session_messages_api_router)
    return TestClient(app)


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> _FakeStore:
    fake = _FakeStore()
    monkeypatch.setattr(session_history, "session_store", lambda: fake)
    return fake


###############################################################################
def test_reads_history_without_requiring_a_room(
    client: TestClient, store: _FakeStore
) -> None:
    """进程内没有房间时回退用用户名当局号，历史依然读得到。"""
    response = client.get(
        PATH.format(user_name="alice"), params={"last_sequence_id": 7}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_messages"][0]["sequence_id"] == 8
    assert store.calls == [
        {"room_id": "alice", "viewer": "alice", "after": 7, "limit": 500}
    ]


def test_limit_is_forwarded(client: TestClient, store: _FakeStore) -> None:
    client.get(
        PATH.format(user_name="alice"),
        params={"last_sequence_id": 0, "limit": 10},
    )

    assert store.calls[0]["limit"] == 10


def test_last_sequence_id_is_required(client: TestClient, store: _FakeStore) -> None:
    response = client.get(PATH.format(user_name="alice"))

    assert response.status_code == 422
