"""pass 编排：快照 → 执行 → 失败回滚。"""

import uuid
from typing import Iterator

import pytest

from ai_srpg.entitas import ExecuteProcessor, ProcessorPipeline, StopPipeline
from ai_srpg.game.assembly import create_srpg_game
from ai_srpg.game.context import SRPGGame
from ai_srpg.gameplay.runtime import run_game_pass, run_room_pass
from ai_srpg.llm.call_context import LlmCallTrace, current_llm_trace
from ai_srpg.pgsql import pgsql_ensure_database_tables
from ai_srpg.pgsql.client import SessionLocal
from ai_srpg.pgsql.game_snapshot import GameSnapshotDB
from ai_srpg.pgsql.game_snapshot_operations import list_game_snapshot_ids
from ai_srpg.session.player_session import PlayerSession
from ai_srpg.session.registry import RoomRegistry
from ai_srpg.session.room import Room
from ai_srpg.session.runtime import bind_runtime_room_registry


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
        db.query(GameSnapshotDB).filter(GameSnapshotDB.room_id == name).delete()
        db.commit()
    finally:
        db.close()


def _room_with(game: SRPGGame, room_id: str) -> Room:
    room = Room(room_id=room_id, owner=room_id)
    room.attach_session(PlayerSession(user_name=room_id, room_id=room_id))
    room.start_game(game=game)
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

    server = RoomRegistry()
    room = await server.create_room(user_name)
    room.attach_session(PlayerSession(user_name=user_name, room_id=room.room_id))
    room.start_game(game=game)
    bind_runtime_room_registry(server)

    result = await run_game_pass(user_name)

    assert result.completed
    # 一条执行前（回滚基线）+ 一条结果（当前状态）
    assert len(list_game_snapshot_ids(user_name, "Game1")) == 2


async def test_run_game_pass_failure_keeps_only_pre_run_snapshot(
    user_name: str,
) -> None:
    game = create_srpg_game(name="Game1")
    game.pipeline = ProcessorPipeline()
    game.pipeline.add(_CreateThenFail(game))

    server = RoomRegistry()
    room = await server.create_room(user_name)
    room.attach_session(PlayerSession(user_name=user_name, room_id=room.room_id))
    room.start_game(game=game)
    bind_runtime_room_registry(server)

    with pytest.raises(RuntimeError, match="boom"):
        await run_game_pass(user_name)

    assert game.entity_count == 0
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


class _HandledRecoverableFailure(ExecuteProcessor):
    """模拟 system 内部处理可恢复失败，并写入状态后正常返回。"""

    def __init__(self, game: SRPGGame, entity_name: str) -> None:
        self._game = game
        self._entity_name = entity_name
        self.handled = False

    async def execute(self) -> None:
        try:
            raise RuntimeError("recoverable llm failure")
        except RuntimeError:
            self.handled = True
            self._game.create_entity(self._entity_name)


class _StopAfterMutation(ExecuteProcessor):
    """模拟 system 完成一部分工作后显式提前结束。"""

    def __init__(self, game: SRPGGame, entity_name: str) -> None:
        self._game = game
        self._entity_name = entity_name

    async def execute(self) -> None:
        self._game.create_entity(self._entity_name)
        raise StopPipeline("intentional early end")


async def test_recoverable_failure_handled_inside_system_does_not_rollback(
    user_name: str,
) -> None:
    game = create_srpg_game(name="Game1")
    game.pipeline = ProcessorPipeline()
    handler = _HandledRecoverableFailure(game, "已处理失败的实体")
    game.pipeline.add(handler)
    game.pipeline.add(_Noop())
    room = _room_with(game, user_name)

    result = await run_room_pass(room)

    assert handler.handled
    assert result.completed
    assert game.get_entity_by_name("已处理失败的实体") is not None
    assert len(list_game_snapshot_ids(user_name, "Game1")) == 1


async def test_swallowed_failure_still_rolls_back_when_later_system_fails(
    user_name: str,
) -> None:
    game = create_srpg_game(name="Game1")
    game.pipeline = ProcessorPipeline()
    game.pipeline.add(_HandledRecoverableFailure(game, "已处理失败的实体"))
    game.pipeline.add(_CreateThenFail(game))
    room = _room_with(game, user_name)

    with pytest.raises(RuntimeError, match="boom"):
        await run_room_pass(room)

    assert game.get_entity_by_name("已处理失败的实体") is None
    assert game.entity_count == 0
    assert len(list_game_snapshot_ids(user_name, "Game1")) == 1


async def test_stop_pipeline_after_mutation_does_not_rollback(user_name: str) -> None:
    game = create_srpg_game(name="Game1")
    game.pipeline = ProcessorPipeline()
    game.pipeline.add(_StopAfterMutation(game, "提前结束的实体"))
    room = _room_with(game, user_name)

    result = await run_room_pass(room)

    assert result.aborted_by == "_StopAfterMutation"
    assert game.get_entity_by_name("提前结束的实体") is not None
    assert len(list_game_snapshot_ids(user_name, "Game1")) == 1
