"""记忆导出：一个实体一个文件，标题只有一层，正文原样放在代码块里。

正文进代码块是为了保真：提示词里自带标题和列表，直接铺进文档会和文档自身的结构打架
（多个一级标题、重复标题、列表前后缺空行）。放进代码块后，读到的就是原样文本。
"""

import re
from pathlib import Path
from typing import List

import pytest

from ai_srpg.game.context import SRPGGame
from ai_srpg.game.memory import get_agent_memory, insert_messages
from ai_srpg.game.memory_dump import dump_memories, memory_markdown
from ai_srpg.models import AIMessage, HumanMessage, ToolMessage
from world_fixture import HERE, OTHER, SENTRY, build_world, entity


def _remember(game: SRPGGame, name: str, contents: List[str]) -> None:
    actor = entity(game, name)
    insert_messages(
        game,
        actor,
        len(get_agent_memory(game, actor).messages),
        [HumanMessage(content=content) for content in contents],
    )


_FENCE = re.compile(r"^`{3,}[A-Za-z]*$")


def _outside_fences(markdown: str) -> List[str]:
    """只留代码块之外的正文行：代码块里的 # 不是标题。"""
    lines: List[str] = []
    in_fence = False
    for line in markdown.splitlines():
        if _FENCE.match(line.strip()):
            in_fence = not in_fence
            continue
        if not in_fence:
            lines.append(line)
    return lines


###############################################################################
# 文件划分
###############################################################################
def test_one_file_per_entity(tmp_path: Path) -> None:
    game = build_world()

    written = dump_memories(game, tmp_path)

    assert len(written) == len(game.agent_memory_store.snapshot())
    assert all(path.parent == tmp_path for path in written)
    assert {path.stem for path in written} == set(game.agent_memory_store.snapshot())


def test_written_order_follows_the_world_hierarchy(tmp_path: Path) -> None:
    """顺序由层级决定，不随调用方给的参数顺序变。"""
    game = build_world()

    written = dump_memories(game, tmp_path, names=[HERE, SENTRY])

    kinds = [path.stem.split(".")[0] for path in written]
    assert kinds == sorted(kinds, key=["世界", "舞台", "角色"].index)


def test_unknown_name_is_reported_with_the_known_ones() -> None:
    game = build_world()

    with pytest.raises(LookupError) as error:
        memory_markdown(game, "角色.没这个人")

    assert "角色.没这个人" in str(error.value)


###############################################################################
# 单份文档的形状
###############################################################################
def test_markdown_has_exactly_one_top_level_heading() -> None:
    game = build_world()
    _remember(game, HERE, ["# 这是正文里的一级标题"])

    markdown = memory_markdown(game, HERE)

    top_level = [line for line in _outside_fences(markdown) if line.startswith("# ")]
    assert top_level == [f"# {HERE}"]


def test_message_headings_are_numbered_so_they_never_repeat() -> None:
    game = build_world()
    _remember(game, HERE, ["一", "二", "三"])

    markdown = memory_markdown(game, HERE)
    headings = [line for line in _outside_fences(markdown) if line.startswith("## ")]

    assert len(headings) == len(set(headings))
    assert headings[0].startswith("## 1 · ")
    assert headings[1] == "## 2 · 输入（human）"


def test_content_keeps_its_original_text_inside_a_fence() -> None:
    """正文里的标题、列表不参与文档结构，所以能原样保留。"""
    game = build_world()
    content = "# 舞台.营地\n\n在场角色：\n- 角色.甲\n- 角色.乙"
    _remember(game, HERE, [content])

    markdown = memory_markdown(game, HERE)

    assert content in markdown
    assert "```text" in markdown


def test_fence_is_longer_than_any_backtick_run_in_the_body() -> None:
    """正文里出现 ``` 时不能提前收尾。"""
    game = build_world()
    _remember(game, HERE, ["看这段：```python\nprint(1)\n```"])

    markdown = memory_markdown(game, HERE)

    assert "````text" in markdown


def test_messages_keep_their_own_order() -> None:
    game = build_world()
    _remember(game, HERE, ["第一句", "第二句", "第三句"])

    markdown = memory_markdown(game, HERE)

    assert (
        markdown.index("第一句") < markdown.index("第二句") < markdown.index("第三句")
    )


def test_tool_calls_are_rendered_so_the_verb_is_visible() -> None:
    game = build_world()
    actor = entity(game, HERE)
    insert_messages(
        game,
        actor,
        len(get_agent_memory(game, actor).messages),
        [
            AIMessage(
                content="（他抬头看了一眼）",
                additional_kwargs={
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "speak",
                                "arguments": '{"content": "火还能撑多久？"}',
                            },
                        }
                    ]
                },
            ),
            ToolMessage(content="（已记下）", tool_call_id="call_1"),
        ],
    )

    markdown = memory_markdown(game, HERE)

    assert '→ speak {"content": "火还能撑多久？"}' in markdown
    assert "## 3 · 回执（tool）" in markdown


def test_every_actor_gets_its_own_document(tmp_path: Path) -> None:
    game = build_world()
    _remember(game, HERE, ["甲说的话"])
    _remember(game, OTHER, ["乙说的话"])

    dump_memories(game, tmp_path)

    here_doc = (tmp_path / f"{HERE}.md").read_text(encoding="utf-8")
    other_doc = (tmp_path / f"{OTHER}.md").read_text(encoding="utf-8")
    assert "甲说的话" in here_doc and "乙说的话" not in here_doc
    assert "乙说的话" in other_doc and "甲说的话" not in other_doc
