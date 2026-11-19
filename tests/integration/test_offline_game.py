"""离线一局：蓝图加载、快照恢复与无房间 pass。"""

import uuid
from pathlib import Path
from typing import Iterator

import pytest

from ai_srpg.entitas import ExecuteProcessor, ProcessorPipeline
from ai_srpg.game.context import SRPGGame
from ai_srpg.gameplay.offline import (
    GameAlreadyExistsError,
    OfflinePassFailed,
    create_new_game,
    list_snapshots,
    load_or_create_game,
    run_offline_pass,
    save_game_snapshot,
)
from ai_srpg.gameplay.runtime import run_pass
from ai_srpg.models import Blueprint, walk_stages
from ai_srpg.pgsql import pgsql_ensure_database_tables
from ai_srpg.pgsql.client import SessionLocal
from ai_srpg.pgsql.game_snapshot import GameSnapshotDB
from ai_srpg.pgsql.game_snapshot_operations import list_game_snapshot_ids
from seeds import create_blueprint


class _Noop(ExecuteProcessor):
    async def execute(self) -> None:
        return None


class _CreateEntity(ExecuteProcessor):
    def __init__(self, game: SRPGGame) -> None:
        self._game = game

    async def execute(self) -> None:
        self._game.create_entity("推进实体")


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
def blueprint() -> Blueprint:
    """默认剧本：断言里的实体名从这里取，不手抄内容。"""
    return create_blueprint("dark_fantasy/mercenary_camp", "Game1")


@pytest.fixture
def blueprint_dir(
    blueprint: Blueprint, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    (tmp_path / "Game1.json").write_text(
        blueprint.model_dump_json(indent=2), encoding="utf-8"
    )
    monkeypatch.setattr("ai_srpg.game.offline.BLUEPRINTS_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def user_name() -> Iterator[str]:
    name = f"test-offline-{uuid.uuid4()}"
    yield name
    db = SessionLocal()
    try:
        db.query(GameSnapshotDB).filter(GameSnapshotDB.room_id == name).delete()
        db.commit()
    finally:
        db.close()


async def test_create_from_blueprint_writes_baseline_snapshot(
    blueprint_dir: Path, blueprint: Blueprint, user_name: str
) -> None:
    game = await load_or_create_game(user_name, "Game1")

    assert game.entity_count > 0
    for stage, _ in walk_stages(blueprint.stage_tree):
        assert game.get_entity_by_name(stage.name) is not None
    for actor in blueprint.actors:
        assert game.get_entity_by_name(actor.name) is not None
    assert len(list_game_snapshot_ids(user_name, "Game1")) == 1

    infos = list_snapshots(user_name, "Game1")
    assert len(infos) == 1
    assert infos[0].entity_count == game.entity_count
    assert infos[0].memory_count > 0


async def test_create_new_game_rejects_existing_unless_reset(
    blueprint_dir: Path, user_name: str
) -> None:
    await create_new_game(user_name, "Game1")

    with pytest.raises(GameAlreadyExistsError, match="已有 1 个快照"):
        await create_new_game(user_name, "Game1")

    outcome = await create_new_game(user_name, "Game1", reset=True)
    assert outcome.snapshot_id
    assert len(list_game_snapshot_ids(user_name, "Game1")) == 2


async def test_load_latest_restores_state(blueprint_dir: Path, user_name: str) -> None:
    game = await load_or_create_game(user_name, "Game1")
    game.create_entity("新实体")
    save_game_snapshot(user_name, game)

    reloaded = await load_or_create_game(user_name, "Game1")

    assert reloaded.get_entity_by_name("新实体") is not None
    assert list_game_snapshot_ids(user_name, "Game1")


async def test_explicit_snapshot_id_is_scoped_to_room(
    blueprint_dir: Path, user_name: str
) -> None:
    await load_or_create_game(user_name, "Game1")
    snapshot_id = list_game_snapshot_ids(user_name, "Game1")[0]

    loaded = await load_or_create_game(user_name, "Game1", snapshot_id=snapshot_id)
    assert loaded.entity_count > 0

    with pytest.raises(LookupError):
        await load_or_create_game("other-user", "Game1", snapshot_id=snapshot_id)


async def test_missing_blueprint_raises(blueprint_dir: Path, user_name: str) -> None:
    with pytest.raises(FileNotFoundError):
        await load_or_create_game(user_name, "NoSuchGame")


async def test_run_pass_without_room_saves_snapshot(
    blueprint_dir: Path, user_name: str
) -> None:
    game = await load_or_create_game(user_name, "Game1")
    game.pipeline = ProcessorPipeline()
    game.pipeline.add(_Noop())

    result = await run_pass(game, user_name)

    assert result.completed
    assert len(list_game_snapshot_ids(user_name, "Game1")) == 2


async def test_offline_pass_saves_success_state(
    blueprint_dir: Path, user_name: str
) -> None:
    game = await load_or_create_game(user_name, "Game1")
    game.pipeline = ProcessorPipeline()
    game.pipeline.add(_CreateEntity(game))

    outcome = await run_offline_pass(game, user_name)

    assert outcome.result.completed
    reloaded = await load_or_create_game(user_name, "Game1")
    assert reloaded.get_entity_by_name("推进实体") is not None


async def test_failing_pass_without_room_rolls_back(
    blueprint_dir: Path, user_name: str
) -> None:
    game = await load_or_create_game(user_name, "Game1")
    game.pipeline = ProcessorPipeline()
    game.pipeline.add(_CreateThenFail(game))

    with pytest.raises(OfflinePassFailed, match="boom"):
        await run_offline_pass(game, user_name)

    assert game.get_entity_by_name("临时实体") is None
    assert len(list_game_snapshot_ids(user_name, "Game1")) == 2
