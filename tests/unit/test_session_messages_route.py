"""会话历史路由测试：只验证契约与参数透传，不访问数据库。"""

from typing import Any, Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_srpg.models import NoneEvent, SessionMessage
from ai_srpg.services.api import session_messages as module
from ai_srpg.services.api.session_messages import session_messages_api_router

PATH = "/api/session_messages/v1/{user_name}/since"


###############################################################################
class _FakeStore:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def latest_sequence(self, user_name: str) -> int:
        return 0

    def append(self, user_name: str, message: SessionMessage) -> None:
        return None

    def messages_since(
        self, user_name: str, after_sequence_id: int, *, limit: int = 500
    ) -> List[SessionMessage]:
        self.calls.append(
            {
                "user_name": user_name,
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
    app.include_router(session_messages_api_router)
    return TestClient(app)


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> _FakeStore:
    fake = _FakeStore()
    monkeypatch.setattr(module, "_session_store", lambda: fake)
    return fake


###############################################################################
def test_reads_history_without_requiring_a_room(
    client: TestClient, store: _FakeStore
) -> None:
    response = client.get(
        PATH.format(user_name="alice"), params={"last_sequence_id": 7}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_messages"][0]["sequence_id"] == 8
    assert store.calls == [{"user_name": "alice", "after": 7, "limit": 500}]


def test_limit_is_forwarded(client: TestClient, store: _FakeStore) -> None:
    client.get(
        PATH.format(user_name="alice"),
        params={"last_sequence_id": 0, "limit": 10},
    )

    assert store.calls[0]["limit"] == 10


def test_last_sequence_id_is_required(client: TestClient, store: _FakeStore) -> None:
    response = client.get(PATH.format(user_name="alice"))

    assert response.status_code == 422
