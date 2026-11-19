"""蓝图产物重建命令：写蓝图 JSON 与提示词留痕，不动数据库。"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from ai_srpg.models import Blueprint
from scripts.build_blueprint import build_blueprint_artifacts, main

SOURCE = "dark_fantasy/nameless_camp"


@pytest.fixture()
def output_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """把两份产物都指向临时目录，避免污染仓库。"""
    monkeypatch.setattr("scripts.build_blueprint.BLUEPRINTS_DIR", tmp_path / "bp")
    monkeypatch.setattr("ai_srpg.game.prompt_dump.PROMPTS_DIR", tmp_path / "prompts")
    return tmp_path


###############################################################################
def test_writes_blueprint_and_prompt_trace(output_dirs: Path) -> None:
    """一次调用产出蓝图文件与提示词留痕两份产物。"""
    path = build_blueprint_artifacts(SOURCE, "Check")

    assert path == output_dirs / "bp" / "Check.json"
    blueprint = Blueprint.model_validate_json(path.read_text(encoding="utf-8"))
    assert blueprint.name == "Check"
    assert (output_dirs / "prompts" / "Check" / "index.md").is_file()


###############################################################################
def test_lists_sources() -> None:
    """--list 给出可选内容源，不产生任何文件。"""
    result = CliRunner().invoke(main, ["--list"])

    assert result.exit_code == 0
    assert SOURCE in result.output


###############################################################################
def test_missing_source_is_a_usage_error() -> None:
    """不指定内容源时不猜默认值，直接报用法错误并列出可选项。"""
    result = CliRunner().invoke(main, [])

    assert result.exit_code != 0
    assert SOURCE in result.output


###############################################################################
def test_unknown_source_is_rejected(output_dirs: Path) -> None:
    """未知内容源列出可选项，而不是静默产出别的内容。"""
    with pytest.raises(KeyError, match="dark_fantasy/nameless_camp"):
        build_blueprint_artifacts("dark_fantasy/space_marine", "Check")
