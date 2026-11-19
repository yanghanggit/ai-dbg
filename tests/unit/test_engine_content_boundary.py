"""守卫「引擎不含内容」：引擎源码不得引用种子数据，也不得出现蓝图里的实体名。

引擎执行机制，故事由蓝图提供。源码里一旦长出具体故事的名词，或反向依赖种子
模块，「换故事不换引擎」就不成立了。题材词汇无法穷举，这里只把两条可机械判断
的边界钉住。

→ 参见：docs/wiki/content-agnostic-engine.md
"""

from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = ROOT / "src" / "ai_srpg"


def _engine_sources() -> List[Path]:
    return sorted(
        path for path in ENGINE_DIR.rglob("*.py") if "__pycache__" not in path.parts
    )


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


###############################################################################
def test_engine_does_not_reference_seed_data() -> None:
    """依赖方向单向：引擎不认识种子模块。"""
    offenders = [
        _relative(path)
        for path in _engine_sources()
        if "seeds" in path.read_text(encoding="utf-8")
    ]

    assert (
        offenders == []
    ), "引擎源码引用了种子数据（引擎应当对故事内容无感）：" + "、".join(offenders)


###############################################################################
def test_engine_source_contains_no_blueprint_entity_names(tmp_path: Path) -> None:
    """蓝图里的实体全名只属于内容侧，不得写进引擎。"""
    from seeds import create_blueprint

    blueprint = create_blueprint(
        "dark_fantasy/nameless_camp", "BoundaryCheck", trace_dir=tmp_path
    )
    names = [world.name for world in blueprint.world_entities]
    for stage in blueprint.stages:
        names.append(stage.name)
        names.extend(actor.name for actor in stage.actors)

    offenders = [
        f"{_relative(path)} → {name}"
        for path in _engine_sources()
        for name in names
        if name in path.read_text(encoding="utf-8")
    ]

    assert (
        offenders == []
    ), "引擎源码出现了蓝图里的实体名（故事内容混进了引擎）：" + "；".join(offenders)
