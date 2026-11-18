"""LLM 调用记录的分析上下文。

记录本身只描述「发了什么、回了什么」；要按对局、命令、agent loop 切片，
还需要一层调用方可知的元数据。这里用 contextvar 传递，避免把 trace 参数
塞进每一次 ``ChatCompletionRequest``。

用法：

    with llm_call_trace(scope="cli", scope_id=str(os.getpid()), user="alice"):
        await service.complete(request)

嵌套时新字段覆盖旧字段，退出后自动恢复外层值。
"""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Iterator, Optional

from pydantic import BaseModel


############################################################################################################
class LlmCallTrace(BaseModel):
    """一次调用所属的分析维度；没有值的字段保持默认。"""

    scope: str = ""  # "cli" / "room"
    scope_id: str = ""  # CLI pid / room 名；用于记录文件切分
    user: str = ""
    game: str = ""
    command: str = ""
    room: str = ""
    job_id: Optional[int] = None
    snapshot_id: Optional[int] = None
    loop_id: str = ""
    round: int = 0
    agent: str = ""
    entity: str = ""


############################################################################################################
_current_trace: ContextVar[LlmCallTrace] = ContextVar(
    "current_llm_call_trace", default=LlmCallTrace()
)


def current_llm_trace() -> LlmCallTrace:
    """返回当前上下文中的 trace；没有设置时返回空 trace。"""
    return _current_trace.get()


############################################################################################################
@contextmanager
def llm_call_trace(
    *,
    scope: Optional[str] = None,
    scope_id: Optional[str] = None,
    user: Optional[str] = None,
    game: Optional[str] = None,
    command: Optional[str] = None,
    room: Optional[str] = None,
    job_id: Optional[int] = None,
    snapshot_id: Optional[int] = None,
    loop_id: Optional[str] = None,
    round: Optional[int] = None,
    agent: Optional[str] = None,
    entity: Optional[str] = None,
) -> Iterator[LlmCallTrace]:
    """在 with 块内合并 trace 字段，退出时恢复外层值。"""
    updates: Dict[str, Any] = {
        key: value
        for key, value in {
            "scope": scope,
            "scope_id": scope_id,
            "user": user,
            "game": game,
            "command": command,
            "room": room,
            "job_id": job_id,
            "snapshot_id": snapshot_id,
            "loop_id": loop_id,
            "round": round,
            "agent": agent,
            "entity": entity,
        }.items()
        if value is not None
    }
    merged = LlmCallTrace.model_validate(
        {**current_llm_trace().model_dump(), **updates}
    )
    token = _current_trace.set(merged)
    try:
        yield merged
    finally:
        _current_trace.reset(token)


__all__ = ["LlmCallTrace", "current_llm_trace", "llm_call_trace"]
