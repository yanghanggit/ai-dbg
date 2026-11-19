"""game_snapshots 持久化：追加、最新读取、按 id 回读与历史列表。"""

import uuid
from typing import Iterator

import pytest

from ai_srpg.game.assembly import create_srpg_game
from ai_srpg.game.context import SRPGGame
from ai_srpg.game.entities import build_from_blueprint
from ai_srpg.game.lifecycle import snapshot_game
from ai_srpg.models import GameSnapshot
from ai_srpg.pgsql import pgsql_ensure_database_tables
from ai_srpg.pgsql.client import SessionLocal
from ai_srpg.pgsql.game_snapshot import GameSnapshotDB
from ai_srpg.pgsql.game_snapshot_operations import (
    append_game_snapshot,
    list_game_snapshot_ids,
    load_game_snapshot,
    load_latest_game_snapshot,
)
from seeds import create_blueprint

GAME_NAME = "Game1"


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema() -> None:
    pgsql_ensure_database_tables()


@pytest.fixture
def user_name() -> Iterator[str]:
    name = f"test-snapshot-{uuid.uuid4()}"
    yield name
    db = SessionLocal()
    try:
        db.query(GameSnapshotDB).filter(GameSnapshotDB.room_id == name).delete()
        db.commit()
    finally:
        db.close()


def _build_game() -> SRPGGame:
    game = create_srpg_game(name=GAME_NAME)
    build_from_blueprint(
        game,
        create_blueprint("dark_fantasy/nameless_camp", GAME_NAME),
        user_name="alice",
    )
    return game


def test_append_and_load_history(user_name: str) -> None:
    game = _build_game()
    first = snapshot_game(game)

    game.create_entity("临时实体")
    second = snapshot_game(game)

    first_id = append_game_snapshot(user_name, first)
    second_id = append_game_snapshot(user_name, second)
    assert second_id > first_id

    latest = load_latest_game_snapshot(user_name, GAME_NAME)
    assert latest is not None
    assert latest == second

    replayed = load_game_snapshot(first_id)
    assert replayed is not None
    assert replayed == first
    assert "临时实体" not in replayed.ecs.entities
    assert "临时实体" in latest.ecs.entities

    ids = list_game_snapshot_ids(user_name, GAME_NAME)
    assert ids == [second_id, first_id]


def test_load_missing_snapshot_returns_none(user_name: str) -> None:
    assert load_latest_game_snapshot(user_name, "NoSuchGame") is None
    assert load_game_snapshot(999_999_999) is None


def test_snapshot_json_roundtrip_through_db(user_name: str) -> None:
    game = _build_game()
    snapshot = snapshot_game(game)
    snapshot_id = append_game_snapshot(user_name, snapshot)

    loaded = load_game_snapshot(snapshot_id)
    assert isinstance(loaded, GameSnapshot)
    assert loaded == snapshot
    # JSONB 会规范化 key 顺序，比较 dict 而不是字符串。
    assert loaded.model_dump() == snapshot.model_dump()
