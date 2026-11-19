"""种子内容包：故事 / 剧本两层，构成引擎的输入侧。

引擎不认识这里；只有开发脚本与测试引用本包。一套故事共用战役设定与全局规则，
故事下可以有多个剧本（不同起点、不同阶段），每个剧本装配一份蓝图。

本包负责所有内容源共用的出厂处理：悬空世界引用校验与提示词留痕。
"""

import re
from pathlib import Path
from typing import Callable, Dict, Final, Iterator, Optional, Tuple

from ai_srpg.game.prompt_dump import dump_blueprint_prompts
from ai_srpg.models import Blueprint

from . import dark_fantasy

#: 故事名 → 该故事的剧本表
_STORY_SCENARIOS: Final[Dict[str, Dict[str, Callable[[str], Blueprint]]]] = {
    "dark_fantasy": dark_fantasy.SCENARIOS,
}

#: 内容源（``故事/剧本``）→ 蓝图构建入口
BLUEPRINT_SOURCES: Final[Dict[str, Callable[[str], Blueprint]]] = {
    f"{story}/{scenario}": builder
    for story, scenarios in _STORY_SCENARIOS.items()
    for scenario, builder in scenarios.items()
}

#: prompt 里对世界实体的引用（只用于检出悬空引用，不参与任何路由）
_WORLD_ENTITY_REF_PATTERN: Final[re.Pattern[str]] = re.compile(r"世界\.\w+")


###############################################################################
def _iter_prompt_messages(blueprint: Blueprint) -> Iterator[Tuple[str, str]]:
    """遍历蓝图里所有实体的 (实体名, system_message)。"""
    for stage in blueprint.stages:
        yield stage.name, stage.system_message
        for actor in stage.actors:
            yield actor.name, actor.system_message
    for world in blueprint.world_entities:
        yield world.name, world.system_message


###############################################################################
def _check_world_references(blueprint: Blueprint) -> None:
    """prompt 中出现的「世界.X」必须是蓝图里真实存在的世界实体。

    世界实体名只用于系统路由；写在故事层 prompt 里一旦改名不会有任何报错，
    prompt 只是悄悄指向一个不存在的实体。校验放在出厂处，构建时直接失败。
    """
    known = {world.name for world in blueprint.world_entities}
    dangling = [
        f"{entity_name} → {ref}"
        for entity_name, message in _iter_prompt_messages(blueprint)
        for ref in _WORLD_ENTITY_REF_PATTERN.findall(message)
        if ref not in known
    ]
    assert (
        not dangling
    ), "prompt 引用了不存在的世界实体（改名后会静默失效）：" + "；".join(dangling)


###############################################################################
def create_blueprint(
    source: str, game_name: str, *, trace_dir: Optional[Path] = None
) -> Blueprint:
    """按内容源（``故事/剧本``）构建蓝图，并跑出厂校验与提示词留痕。

    ``trace_dir`` 指定留痕目录，缺省导出到 ``logs/blueprints/<game_name>/``。
    """
    builder = BLUEPRINT_SOURCES.get(source)
    if builder is None:
        raise KeyError(f"未知内容源: {source}；可选: {sorted(BLUEPRINT_SOURCES)}")

    blueprint = builder(game_name)
    _check_world_references(blueprint)
    dump_blueprint_prompts(blueprint, directory=trace_dir)
    return blueprint


###############################################################################
__all__ = ["BLUEPRINT_SOURCES", "create_blueprint"]
