"""把带记忆的实体各导出成一份 markdown，一个文件对应一个实体。

记忆是角色全部上下文的累积：看它，比看单次调用记录更容易判断「它为什么这么说」。
一个实体一个文件，标题只有一层，消息按发生顺序编号；消息正文一律放在代码块里，
所以提示词里的标题、列表、缩进不会和文档自身的结构打架，读到的就是原样文本。
"""

from pathlib import Path
from typing import Dict, List, Optional, Sequence

from ..models import ChatMessage
from .context import SRPGGame

#: 分组顺序：先世界，再舞台，最后角色
_KIND_ORDER: Dict[str, int] = {"世界": 0, "舞台": 1, "角色": 2}

#: LLM 消息类型的中文标签；未知类型原样输出
_TYPE_LABELS: Dict[str, str] = {
    "system": "系统",
    "human": "输入",
    "ai": "回复",
    "tool": "回执",
    "function": "调用",
}


###############################################################################
def _kind_rank(name: str) -> int:
    prefix = name.split(".")[0]
    return _KIND_ORDER.get(prefix, len(_KIND_ORDER))


###############################################################################
def _ordered_names(
    srpg_game: SRPGGame, names: Optional[Sequence[str]] = None
) -> List[str]:
    """按「世界 → 舞台 → 角色」排序，同类按名字排序；``names`` 只是筛选。"""
    memories = srpg_game.agent_memory_store.snapshot()
    if names:
        missing = [name for name in names if name not in memories]
        if missing:
            raise LookupError(
                "这些实体没有记忆: "
                + "、".join(missing)
                + "；已知有记忆的: "
                + "、".join(sorted(memories))
            )
    else:
        names = list(memories)
    return sorted(names, key=lambda item: (_kind_rank(item), item))


###############################################################################
def _fence(text: str) -> str:
    """比正文里最长的反引号串更长，正文里有 ``` 也不会提前收尾。"""
    longest = 0
    run = 0
    for char in text:
        run = run + 1 if char == "`" else 0
        longest = max(longest, run)
    return "`" * max(3, longest + 1)


###############################################################################
def _body(message: ChatMessage) -> str:
    """消息原文；工具调用接在正文后面，看得出这一轮选了什么动词、什么参数。"""
    lines = [message.content] if message.content else []
    calls = (message.additional_kwargs or {}).get("tool_calls") or []
    for call in calls:
        function = call.get("function", {})
        lines.append(
            " ".join(
                [f"→ {function.get('name', '?')}", function.get("arguments", "")]
            ).rstrip()
        )
    return "\n".join(lines)


###############################################################################
def _render_message(index: int, message: ChatMessage) -> str:
    label = _TYPE_LABELS.get(message.type, message.type)
    body = _body(message)
    fence = _fence(body)
    opening = f"{fence}text"
    return "\n".join(
        [f"## {index} · {label}（{message.type}）", "", opening, body, fence]
    )


###############################################################################
def memory_markdown(srpg_game: SRPGGame, name: str) -> str:
    """一个实体的整份记忆：标题、条数、逐条消息。"""
    memory = srpg_game.agent_memory_store.get(name)
    if memory is None:
        raise LookupError(f"没有这个实体的记忆: {name}")
    messages = list(memory.messages)
    header = "\n".join([f"# {name}", "", f"{len(messages)} 条消息，按发生顺序排列。"])
    body = "\n\n".join(
        _render_message(index, message) for index, message in enumerate(messages, 1)
    )
    return "\n\n".join([header, body]).rstrip() + "\n"


###############################################################################
def dump_memories(
    srpg_game: SRPGGame,
    directory: Path,
    *,
    names: Optional[Sequence[str]] = None,
) -> List[Path]:
    """每个实体写一个 ``<实体名>.md``，返回写出的文件（顺序同上）。"""
    directory.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for name in _ordered_names(srpg_game, names):
        path = directory / f"{name}.md"
        path.write_text(memory_markdown(srpg_game, name), encoding="utf-8")
        written.append(path)
    return written


###############################################################################
__all__ = ["dump_memories", "memory_markdown"]
