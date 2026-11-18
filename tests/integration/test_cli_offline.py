"""CLI 端到端：new → stages → advance → compact → snapshots。"""

import uuid
from pathlib import Path
from typing import Iterator

import pytest
from click.testing import CliRunner

from ai_srpg.cli.srpg_agent_game import main
from ai_srpg.pgsql import pgsql_ensure_database_tables
from ai_srpg.pgsql.client import SessionLocal
from ai_srpg.pgsql.game_snapshot import GameSnapshotDB
from seeds import create_seed_blueprint


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema() -> None:
    pgsql_ensure_database_tables()


@pytest.fixture
def blueprint_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    blueprint = create_seed_blueprint("Game1")
    (tmp_path / "Game1.json").write_text(
        blueprint.model_dump_json(indent=2), encoding="utf-8"
    )
    monkeypatch.setattr("ai_srpg.game.offline.BLUEPRINTS_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def user_name() -> Iterator[str]:
    name = f"test-cli-{uuid.uuid4()}"
    yield name
    db = SessionLocal()
    try:
        db.query(GameSnapshotDB).filter(GameSnapshotDB.user_name == name).delete()
        db.commit()
    finally:
        db.close()


def test_cli_offline_flow(blueprint_dir: Path, user_name: str) -> None:
    runner = CliRunner()

    created = runner.invoke(main, ["new", "--user", user_name, "--game", "Game1"])
    assert created.exit_code == 0, created.output
    assert "entities:" in created.output
    assert "snapshot:" in created.output

    duplicate = runner.invoke(main, ["new", "--user", user_name, "--game", "Game1"])
    assert duplicate.exit_code == 1
    assert "已有 1 个快照" in duplicate.output

    stages = runner.invoke(
        main, ["stages", "--user", user_name, "--game", "Game1", "--json"]
    )
    assert stages.exit_code == 0, stages.output
    assert "场景.营地" in stages.output
    assert "角色.无名" in stages.output

    advanced = runner.invoke(main, ["advance", "--user", user_name, "--game", "Game1"])
    assert advanced.exit_code == 0, advanced.output
    assert "completed:" in advanced.output
    assert "snapshot:" in advanced.output

    compacted = runner.invoke(
        main,
        [
            "compact-context",
            "--user",
            user_name,
            "--game",
            "Game1",
            "--target",
            "角色.无名",
        ],
    )
    assert compacted.exit_code == 0, compacted.output
    assert "messages:" in compacted.output
    assert "snapshot:" in compacted.output

    history = runner.invoke(main, ["snapshots", "--user", user_name, "--game", "Game1"])
    assert history.exit_code == 0, history.output
    assert history.output.count("id=") == 4

    reset = runner.invoke(
        main,
        ["new", "--user", user_name, "--game", "Game1", "--reset"],
    )
    assert reset.exit_code == 0, reset.output
    assert "snapshot:" in reset.output
