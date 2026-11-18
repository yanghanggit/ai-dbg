"""pass 编排：快照 → 执行 → 失败回滚。"""

import uuid
from typing import Iterator

import pytest

from ai_srpg.entitas import ExecuteProcessor, ProcessorPipeline
from ai_srpg.game.assembly import create_srpg_game
from ai_srpg.game.context import SRPGGame
from ai_srpg.llm.call_context import LlmCallTrace, current_llm_trace
from ai_srpg.models import PlayerSession
from ai_srpg.pgsql import pgsql_ensure_database_tables
from ai_srpg.pgsql.client import SessionLocal
from ai_srpg.pgsql.game_snapshot import GameSnapshotDB
from ai_srpg.pgsql.game_snapshot_operations import list_game_snapshot_ids
from ai_srpg.services.game_server_runtime import bind_runtime_game_server
from ai_srpg.services.gameplay_runtime import run_game_pass, run_room_pass
from ai_srpg.session.room import PlayerRoom
from ai_srpg.session.server import GameServer


class _Noop(ExecuteProcessor):
    async def execute(self) -> None:
        return None


class _CaptureTrace(ExecuteProcessor):
    def __init__(self) -> None:
        self.traces: list[LlmCallTrace] = []

    async def execute(self) -> None:
        self.traces.append(current_llm_trace())


class _CreateThenFail(ExecuteProcessor):
    def __init__(self, game: SRPGGame) -> None:
        self._game = game

    async def execute(self) -> None:
        self._game.create_entity("临时实体")
        raise RuntimeError("boom")


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema() -> None:
    pgsql_ensure_database_tables()


@pytest.fixture
def user_name() -> Iterator[str]:
    name = f"test-pass-{uuid.uuid4()}"
    yield name
    db = SessionLocal()
    try:
        db.query(GameSnapshotDB).filter(GameSnapshotDB.user_name == name).delete()
        db.commit()
    finally:
        db.close()


def _room_with(game: SRPGGame, user_name: str) -> PlayerRoom:
    room = PlayerRoom(user_name)
    room.bind(game=game, player_session=PlayerSession(name=user_name))
    return room


async def test_successful_pass_keeps_snapshot_and_state(user_name: str) -> None:
    game = create_srpg_game(name="Game1")
    game.pipeline = ProcessorPipeline()
    game.pipeline.add(_Noop())
    room = _room_with(game, user_name)

    result = await run_room_pass(room)

    assert result.completed
    assert game.entity_count == 0
    assert len(list_game_snapshot_ids(user_name, "Game1")) == 1


async def test_failed_pass_rolls_back_ecs_and_keeps_pre_run_snapshot(
    user_name: str,
) -> None:
    game = create_srpg_game(name="Game1")
    game.pipeline = ProcessorPipeline()
    game.pipeline.add(_CreateThenFail(game))
    room = _room_with(game, user_name)

    with pytest.raises(RuntimeError, match="boom"):
        await run_room_pass(room)

    assert game.entity_count == 0
    assert game.get_entity_by_name("临时实体") is None
    assert len(list_game_snapshot_ids(user_name, "Game1")) == 1


async def test_run_game_pass_acquires_room(user_name: str) -> None:
    game = create_srpg_game(name="Game1")
    game.pipeline = ProcessorPipeline()
    game.pipeline.add(_Noop())

    server = GameServer()
    room = await server.create_room(user_name)
    room.bind(game=game, player_session=PlayerSession(name=user_name))
    bind_runtime_game_server(server)

    result = await run_game_pass(user_name)

    assert result.completed
    assert len(list_game_snapshot_ids(user_name, "Game1")) == 1


async def test_pass_sets_room_trace(user_name: str) -> None:
    game = create_srpg_game(name="Game1")
    game.pipeline = ProcessorPipeline()
    capture = _CaptureTrace()
    game.pipeline.add(capture)
    room = _room_with(game, user_name)

    await run_room_pass(room)

    assert len(capture.traces) == 1
    trace = capture.traces[0]
    assert trace.scope == "room"
    assert trace.scope_id == user_name
    assert trace.user == user_name
    assert trace.game == "Game1"
    assert trace.room == user_name
    assert trace.snapshot_id is not None
