#!/usr/bin/env python3
"""重建蓝图产物：把某个内容源的蓝图写进 ``.blueprints/``，并导出提示词留痕。

    uv run python -m scripts.build_blueprint --source dark_fantasy/mercenary_camp --game Game1
    uv run python -m scripts.build_blueprint --list

产物是 ``.blueprints/<game>.json`` 与 ``logs/blueprints/<game>/``。换故事换剧本、
改设定后只重建产物即可，不必清库；已有快照的局仍按快照恢复。
"""

from pathlib import Path
from typing import Optional

import click
from loguru import logger

from ai_srpg.paths import BLUEPRINTS_DIR, PROMPTS_DIR
from seeds import BLUEPRINT_SOURCES, create_blueprint


###########################################################################################################
def build_blueprint_artifacts(source: str, game_name: str) -> Path:
    """写出蓝图 JSON 并导出提示词留痕，返回蓝图文件路径。"""
    blueprint = create_blueprint(source, game_name)
    path = BLUEPRINTS_DIR / f"{game_name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(blueprint.model_dump_json(indent=4), encoding="utf-8")
    return path


###########################################################################################################
@click.command()
@click.option("--source", default=None, help="内容源「故事/剧本」，可用 --list 查看")
@click.option("--game", default="Game1", show_default=True, help="蓝图名，同时是游戏名")
@click.option("--list", "list_sources", is_flag=True, help="列出可选内容源后退出")
def main(source: Optional[str], game: str, list_sources: bool) -> None:
    """重建蓝图产物。"""
    if list_sources:
        for name in sorted(BLUEPRINT_SOURCES):
            click.echo(name)
        return

    if source is None:
        raise click.UsageError(f"缺少 --source；可选: {sorted(BLUEPRINT_SOURCES)}")

    path = build_blueprint_artifacts(source, game)
    logger.success(f"✅ 蓝图已写入 {path}")
    click.echo(f"提示词留痕: {PROMPTS_DIR / game}")


###########################################################################################################
if __name__ == "__main__":
    main()
