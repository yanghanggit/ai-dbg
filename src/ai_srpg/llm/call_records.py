"""一次 LLM 调用的结构化记录（append-only JSONL）。

开发期用途：查询“这次请求到底发了什么上下文、模型回了什么”，用于排查问题与
调整提示词。每次 chat completion（成功或失败）追加一行到
``.llm_calls/YYYYMMDD.jsonl``；记录可被脚本 / agent 直接解析、过滤、比较，
而不是只能人眼阅读的纯文本。

两级开关（AND，后者是前者的上限）：

1. 请求级：``ChatCompletionRequest.record``——「我想不想留痕」；
2. 进程级：环境变量 ``AI_SRPG_LLM_CALL_LOG_ENABLED``——「这台进程允不允许落盘」。

旧名 ``AI_SRPG_CHAT_DUMP_ENABLED`` 仍兼容（读到会提示一次）。
``request.record=True`` 但进程级关闭时只警告一次再跳过：静默失效比不落盘更糟。
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from loguru import logger
from pydantic import BaseModel, Field

from ..models import HumanMessage
from ..paths import LLM_CALLS_DIR
from .types import ChatCompletionRequest, ChatCompletionResult

############################################################################################################
#: 进程级总开关；未设置视为开启
ENV_CALL_LOG_SWITCH: str = "AI_SRPG_LLM_CALL_LOG_ENABLED"

#: 旧变量名（chat_dump 时代）；只读兼容，命中时提示一次
LEGACY_ENV_CALL_LOG_SWITCH: str = "AI_SRPG_CHAT_DUMP_ENABLED"

#: 记录结构版本；字段变化时递增
SCHEMA_VERSION: int = 1

_FALSE_VALUES: frozenset[str] = frozenset({"0", "false", "no", "off"})

_warned_env_suppressed: bool = False
_warned_legacy_env: bool = False


############################################################################################################
class LlmCallRecord(BaseModel):
    """一次 chat completion 的完整留痕。"""

    schema_version: int = SCHEMA_VERSION
    request_id: str
    created_at: datetime
    label: str
    model: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    context_digest: str
    message_count: int
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    response: Dict[str, Any] = Field(default_factory=dict)
    usage: Optional[Dict[str, Any]] = None
    elapsed_ms: int = 0


############################################################################################################
def env_allows_call_log() -> bool:
    """进程级总开关是否允许记录（默认允许；调用时读取环境变量）。"""
    raw = os.getenv(ENV_CALL_LOG_SWITCH)
    if raw is None:
        raw = os.getenv(LEGACY_ENV_CALL_LOG_SWITCH)
        if raw is not None:
            _warn_legacy_env()
    if raw is None:
        return True
    return raw.strip().lower() not in _FALSE_VALUES


############################################################################################################
def record_llm_call(
    request: ChatCompletionRequest, completion: ChatCompletionResult
) -> Optional[str]:
    """记录一次 LLM 调用；返回 ``request_id``（未记录时返回 ``None``）。

    落盘失败只记 warning，调试旁路不得影响主流程。
    """
    if not request.record:
        return None
    if not env_allows_call_log():
        _warn_env_suppressed()
        return None

    try:
        record = build_llm_call_record(request, completion)
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(record.model_dump_json() + "\n")
        logger.debug(f"llm call recorded: {path} request_id={record.request_id}")
        return record.request_id
    except Exception as e:
        logger.warning(
            f"record_llm_call failed for '{request.label}': {type(e).__name__}: {e}"
        )
        return None


############################################################################################################
def build_llm_call_record(
    request: ChatCompletionRequest, completion: ChatCompletionResult
) -> LlmCallRecord:
    """由值对象构造记录；纯函数，便于测试与将来换 sink。"""
    messages: List[Dict[str, Any]] = [
        message.model_dump(mode="json") for message in request.messages
    ]
    if request.input_message:
        messages.append(
            HumanMessage(content=request.input_message).model_dump(mode="json")
        )

    return LlmCallRecord(
        request_id=uuid.uuid4().hex,
        created_at=datetime.now(timezone.utc),
        label=request.label,
        model=request.model,
        params={
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "thinking": request.thinking,
            "tool_choice": request.tool_choice,
            "reasoning_effort": request.reasoning_effort,
            "timeout": request.timeout,
            "tools": [tool.model_dump(mode="json") for tool in request.tools],
        },
        context_digest=_context_digest(messages),
        message_count=len(messages),
        messages=messages,
        response=_response_payload(completion),
        usage=completion.usage.model_dump(mode="json") if completion.usage else None,
        elapsed_ms=int(completion.elapsed_seconds * 1000),
    )


############################################################################################################
def iter_llm_call_records(
    *,
    label: Optional[str] = None,
    root: Optional[Path] = None,
) -> Iterator[LlmCallRecord]:
    """按时间倒序迭代记录；``label`` 精确匹配。"""
    base = root or LLM_CALLS_DIR
    for path in sorted(base.glob("*.jsonl"), reverse=True):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as e:
            logger.warning(f"读取 llm call 记录失败: {path}: {e}")
            continue
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                record = LlmCallRecord.model_validate_json(line)
            except Exception as e:
                logger.warning(f"跳过损坏的 llm call 记录: {path}: {e}")
                continue
            if label is not None and record.label != label:
                continue
            yield record


############################################################################################################
def find_llm_call(
    request_id: str, *, root: Optional[Path] = None
) -> Optional[LlmCallRecord]:
    """按完整 id 或唯一前缀查找记录。"""
    prefix_matches: List[LlmCallRecord] = []
    for record in iter_llm_call_records(root=root):
        if record.request_id == request_id:
            return record
        if record.request_id.startswith(request_id):
            prefix_matches.append(record)
    return prefix_matches[0] if len(prefix_matches) == 1 else None


############################################################################################################
def _log_path() -> Path:
    return LLM_CALLS_DIR / f"{datetime.now().strftime('%Y%m%d')}.jsonl"


def _context_digest(messages: List[Dict[str, Any]]) -> str:
    payload = json.dumps(messages, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _response_payload(completion: ChatCompletionResult) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "finish_reason": completion.finish_reason,
        "tool_calls": [call.model_dump(mode="json") for call in completion.tool_calls],
        "ai_message": (
            completion.ai_message.model_dump(mode="json")
            if completion.ai_message is not None
            else None
        ),
        "error": None,
    }
    if completion.error is not None:
        payload["error"] = {
            "kind": completion.error.kind,
            "status_code": completion.error.status_code,
            "retryable": completion.error.retryable,
            "message": str(completion.error),
        }
    return payload


def _warn_env_suppressed() -> None:
    """「请求想开、进程级关了」只警告一次。"""
    global _warned_env_suppressed
    if _warned_env_suppressed:
        return
    _warned_env_suppressed = True
    logger.warning(
        f"llm call 记录已被环境变量 {ENV_CALL_LOG_SWITCH} 关闭；"
        "request.record=True 被忽略（本进程不再记录，仅提示一次）"
    )


def _warn_legacy_env() -> None:
    global _warned_legacy_env
    if _warned_legacy_env:
        return
    _warned_legacy_env = True
    logger.warning(
        f"{LEGACY_ENV_CALL_LOG_SWITCH} 已更名为 {ENV_CALL_LOG_SWITCH}，请更新 .env"
    )


__all__ = [
    "ENV_CALL_LOG_SWITCH",
    "LEGACY_ENV_CALL_LOG_SWITCH",
    "SCHEMA_VERSION",
    "LlmCallRecord",
    "build_llm_call_record",
    "env_allows_call_log",
    "find_llm_call",
    "iter_llm_call_records",
    "record_llm_call",
]
