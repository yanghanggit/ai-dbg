"""CLI 端到端：list → new → bind → stages → advance → compact → snapshots。"""

import uuid
from pathlib import Path
from typing import Iterator

import pytest
from click.testing import CliRunner

from ai_srpg.cli.srpg_agent_game import main
from ai_srpg.pgsql import pgsql_ensure_database_tables
from ai_srpg.pgsql.client import SessionLocal
from ai_srpg.pgsql.game_snapshot import GameSnapshotDB
from seeds import create_blueprint


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema() -> None:
    pgsql_ensure_database_tables()


@pytest.fixture
def blueprint_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    blueprint = create_blueprint("dark_fantasy/nameless_camp", "Game1")
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
        db.query(GameSnapshotDB).filter(GameSnapshotDB.room_id == name).delete()
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

    listed = runner.invoke(main, ["list", "--user", user_name])
    assert listed.exit_code == 0, listed.output
    assert "Game1" in listed.output
    assert "snapshots=1" in listed.output

    unknown = runner.invoke(
        main,
        ["bind", "--user", user_name, "--game", "NoSuchGame", "--actor", "角色.无名"],
    )
    assert unknown.exit_code == 1
    assert "先用 new 建局" in unknown.output

    bound = runner.invoke(
        main, ["bind", "--user", user_name, "--game", "Game1", "--actor", "角色.无名"]
    )
    assert bound.exit_code == 0, bound.output
    assert "actor:     角色.无名" in bound.output
    assert "snapshot:" in bound.output

    rebound_to_same = runner.invoke(
        main, ["bind", "--user", user_name, "--game", "Game1", "--actor", "角色.无名"]
    )
    assert rebound_to_same.exit_code == 0, rebound_to_same.output

    missing_actor = runner.invoke(
        main, ["bind", "--user", user_name, "--game", "Game1", "--actor", "角色.不存在"]
    )
    assert missing_actor.exit_code == 1
    assert "找不到角色实体" in missing_actor.output

    stages = runner.invoke(
        main, ["stages", "--user", user_name, "--game", "Game1", "--json"]
    )
    assert stages.exit_code == 0, stages.output
    assert "舞台.营地" in stages.output
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
    # 一次 pass 会落两条快照（执行前用于回滚 + 结果），加上 new、两次 bind、compact
    assert history.output.count("id=") == 6

    reset = runner.invoke(
        main,
        ["new", "--user", user_name, "--game", "Game1", "--reset"],
    )
    assert reset.exit_code == 0, reset.output
    assert "snapshot:" in reset.output
