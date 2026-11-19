"""蓝图 prompt 留痕：把每个实体进 ECS 后的第一条记忆导出成 markdown。

构建蓝图时，``ActorBlueprint`` / ``StageBlueprint`` / ``WorldBlueprint`` 的 ``system_message`` 就是它进游戏后
的 ``memories[0]``（由 ``add_system_message`` 原样写入）。这里在出厂时把同一份文本
按实体落盘，提示词的问题在一开始就能看见，不必等游戏跑起来翻调用记录。

产物布局：``logs/blueprints/<蓝图名>/<实体全名>.md``，外加一份 ``index.md`` 概览。
每次导出先清空同名目录，避免改名或删除实体后留下旧文件。
"""

from pathlib import Path
from typing import List, Optional, Tuple

from loguru import logger

from ..models import Blueprint, walk_stages
from ..paths import PROMPTS_DIR

#: index.md 里的类别标签（与实体全名的前缀一一对应）
_KIND_LABELS = {"world": "世界", "stage": "舞台", "actor": "角色"}


###############################################################################
def _safe_name(name: str) -> str:
    """把实体名/蓝图名收敛成安全的文件与目录名。"""
    cleaned = name.replace("/", "_").replace("\\", "_").strip()
    return cleaned or "unnamed"


###############################################################################
def _prompt_entries(blueprint: Blueprint) -> List[Tuple[str, str, str]]:
    """(类别, 实体全名, system prompt)，顺序：世界 → 舞台 → 角色。"""
    entries: List[Tuple[str, str, str]] = []
    for world in blueprint.world_entities:
        entries.append(("world", world.name, world.system_message))
    for stage, _ in walk_stages(blueprint.root_stage):
        entries.append(("stage", stage.name, stage.system_message))
    for actor in blueprint.actors:
        entries.append(("actor", actor.name, actor.system_message))
    return entries


###############################################################################
def _section_titles(prompt: str) -> str:
    """抽取 prompt 里的标题行，供 index 一眼看出段落构成。"""
    return " / ".join(
        line.lstrip("# ").strip()
        for line in prompt.splitlines()
        if line.startswith("#")
    )


###############################################################################
def dump_blueprint_prompts(
    blueprint: Blueprint, *, directory: Optional[Path] = None
) -> Path:
    """导出蓝图里所有可能带记忆的实体的 system prompt，返回产物目录。"""
    target = directory or PROMPTS_DIR / _safe_name(blueprint.name)

    if target.exists():
        for stale in target.glob("*.md"):
            stale.unlink()
    target.mkdir(parents=True, exist_ok=True)

    entries = _prompt_entries(blueprint)
    index_rows: List[str] = [
        f"# 蓝图 prompt 留痕：{blueprint.name}",
        "",
        "每个实体一份 md，内容即它进 ECS 后的 `memories[0]`。",
        "",
        "| 类别 | 实体 | 字符数 | 段落 |",
        "| --- | --- | --- | --- |",
    ]

    for kind, name, prompt in entries:
        path = target / f"{_safe_name(name)}.md"
        path.write_text(prompt.rstrip() + "\n", encoding="utf-8")
        index_rows.append(
            f"| {_KIND_LABELS[kind]} | {name} | {len(prompt)} | {_section_titles(prompt)} |"
        )

    (target / "index.md").write_text("\n".join(index_rows) + "\n", encoding="utf-8")
    logger.info(f"🧾 蓝图 prompt 已导出: {target}（{len(entries)} 个实体）")
    return target
