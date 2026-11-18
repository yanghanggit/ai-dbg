"""客户端 CLI 测试：命令与输出的接线，不经过网络。"""

from typing import Any, List, Optional

import pytest
from click.testing import CliRunner, Result
from procrastinate.jobs import Status as JobStatus

from ai_srpg.cli import srpg_client
from ai_srpg.services.api.schemas import JobDetail, RoomStateResponse
from ai_srpg.srpg_game_client.core import GameClientError


###############################################################################
class _FakeClient:
    """只实现 CLI 用到的动作，记录调用顺序。"""

    def __init__(self, *, fail_at: Optional[str] = None) -> None:
        self.calls: List[Any] = []
        self._fail_at = fail_at
        self.closed = False

    def _maybe_fail(self, action: str) -> None:
        if self._fail_at == action:
            raise GameClientError(404, "没有房间，请先登录")

    def enter_room(self, user_name: str) -> RoomStateResponse:
        self.calls.append(("enter", user_name))
        self._maybe_fail("enter")
        return RoomStateResponse(user_name=user_name)

    def open_game(self, user_name: str, game_name: str) -> RoomStateResponse:
        self.calls.append(("open", user_name, game_name))
        return RoomStateResponse(user_name=user_name, game=game_name)

    def advance(self, user_name: str, game_name: str) -> int:
        self.calls.append(("advance", user_name, game_name))
        return len(self.calls)

    def wait_job(self, job_id: int, **kwargs: Any) -> JobDetail:
        self.calls.append(("wait", job_id))
        return JobDetail(job_id=job_id, status=JobStatus.SUCCEEDED, events=[])

    def snapshots(self, user_name: str, game_name: str, **kwargs: Any) -> List[Any]:
        return []

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> _FakeClient:
    client = _FakeClient()
    monkeypatch.setattr(srpg_client, "_client", lambda options: client)
    return client


def _run(args: List[str]) -> Result:
    return CliRunner().invoke(srpg_client.main, ["--server", "http://x"] + args)


###############################################################################
def test_play_enters_opens_and_runs_rounds(fake: _FakeClient) -> None:
    result = _run(["play", "alice", "Game1", "--rounds", "2", "--interval", "0"])

    assert result.exit_code == 0, result.output
    assert "round 1:" in result.output
    assert "round 2:" in result.output
    assert [call[0] for call in fake.calls] == [
        "enter",
        "open",
        "advance",
        "wait",
        "advance",
        "wait",
    ]
    assert fake.closed


def test_advance_no_wait_prints_job_id(fake: _FakeClient) -> None:
    result = _run(["advance", "alice", "Game1", "--no-wait"])

    assert result.exit_code == 0, result.output
    assert result.output.strip().startswith("job: ")
    assert ("wait", 1) not in fake.calls


def test_client_error_becomes_click_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        srpg_client, "_client", lambda options: _FakeClient(fail_at="enter")
    )

    result = _run(["enter", "ghost"])

    assert result.exit_code == 1
    assert "没有房间" in result.output


def test_json_output_is_passthrough(fake: _FakeClient) -> None:
    result = CliRunner().invoke(
        srpg_client.main, ["--server", "http://x", "--json", "enter", "alice"]
    )

    assert result.exit_code == 0, result.output
    assert '"user_name": "alice"' in result.output
