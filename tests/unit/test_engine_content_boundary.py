"""守卫「引擎不含内容」：引擎源码不得引用种子数据，也不得出现蓝图里的实体名。

引擎执行机制，故事由蓝图提供。源码里一旦长出具体故事的名词，或反向依赖种子
模块，「换故事不换引擎」就不成立了。题材词汇无法穷举，这里只把两条可机械判断
的边界钉住。

→ 参见：docs/wiki/content-agnostic-engine.md
"""

import re
from pathlib import Path
from typing import Any, Iterator, List

ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = ROOT / "src" / "ai_srpg"

#: 短句（标题、组件键、逗号分隔的短语）本来就是模板的一部分，只查成句的散文
MIN_PROSE_LENGTH = 16

#: 散文按句子切：抄半句也算抄，不必整段照搬才报警
_SENTENCE_END = re.compile(r"[。；！？]")

#: 比对片段的长度：短于此的巧合太多，长于此的只能是照搬
COPY_WINDOW = 14


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
    from ai_srpg.models import walk_stages
    from seeds import create_blueprint

    blueprint = create_blueprint(
        "dark_fantasy/mercenary_camp", "BoundaryCheck", trace_dir=tmp_path
    )
    names = [world.name for world in blueprint.worlds]
    names.extend(stage.name for stage, _ in walk_stages(blueprint.stage_tree))
    names.extend(actor.name for actor in blueprint.actors)

    offenders = [
        f"{_relative(path)} → {name}"
        for path in _engine_sources()
        for name in names
        if name in path.read_text(encoding="utf-8")
    ]

    assert (
        offenders == []
    ), "引擎源码出现了蓝图里的实体名（故事内容混进了引擎）：" + "；".join(offenders)


###############################################################################
def test_engine_prompts_do_not_embed_story_prose(tmp_path: Path) -> None:
    """故事散文只能留在内容侧：引擎里出现蓝图的原句，等于把故事焊进机制。

    实体名挡得住「某个角色」，挡不住「某段设定」——抄一句舞台设定进引擎提示词，
    换故事时这段文字就成了写死在引擎里的场景。按句子的定长片段比对，抄半句也算。
    """
    from seeds import create_blueprint

    blueprint = create_blueprint(
        "dark_fantasy/mercenary_camp", "BoundaryProse", trace_dir=tmp_path
    )
    prose = [
        line.strip()
        for line in _iter_strings(blueprint.model_dump())
        if len(line.strip()) >= MIN_PROSE_LENGTH
    ]

    offenders: List[str] = []
    for path in _engine_sources():
        text = path.read_text(encoding="utf-8")
        for sentence in prose:
            window = _copied_window(sentence, text)
            if window is not None:
                offenders.append(f"{_relative(path)} → {window}…")
                break

    assert (
        offenders == []
    ), "引擎源码抄进了内容侧的故事散文（提示词应当只讲结构与机制）：" + "；".join(
        offenders
    )


###############################################################################
def _copied_window(sentence: str, text: str) -> str | None:
    """返回这句散文里被抄进引擎的片段；没有抄就返回 ``None``。"""
    for start in range(0, len(sentence) - COPY_WINDOW + 1):
        window = sentence[start : start + COPY_WINDOW]
        if window in text:
            return window
    return None


###############################################################################
def _iter_strings(value: Any) -> Iterator[str]:
    """展开蓝图里的每一段文本：设定、system message、组件里的底稿与体型。"""
    if isinstance(value, str):
        for line in value.splitlines():
            yield from _SENTENCE_END.split(line)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_strings(item)
