"""LLM 调用记录（.llm_calls JSONL）：结构、开关与读取。"""

import importlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

import pytest

from ai_srpg.llm.call_context import llm_call_trace
from ai_srpg.llm.call_records import (
    ENV_CALL_LOG_SWITCH,
    LlmCallRecord,
    build_llm_call_record,
    env_allows_call_log,
    find_llm_call,
    iter_llm_call_records,
    record_llm_call,
)
from ai_srpg.llm.errors import ChatError
from ai_srpg.llm.types import (
    ChatCompletionRequest,
    ChatCompletionResult,
    ToolDefinition,
    ToolFunction,
    Usage,
)
from ai_srpg.models import AIMessage, SystemMessage, get_buffer_string


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_CALL_LOG_SWITCH, raising=False)
    module = importlib.import_module("ai_srpg.llm.call_records")
    monkeypatch.setattr(module, "_warned_env_suppressed", False)


@pytest.fixture
def calls_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr("ai_srpg.llm.call_records.LLM_CALLS_DIR", tmp_path)
    return tmp_path


def _ai_with_tool_call() -> AIMessage:
    return AIMessage(
        content="",
        additional_kwargs={
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "get_entity_stats",
                        "arguments": '{"entity_name": "角色.无名"}',
                    },
                }
            ]
        },
    )


def _dummy_tool() -> ToolDefinition:
    return ToolDefinition(
        function=ToolFunction(
            name="f", description="d", parameters={"type": "object", "properties": {}}
        )
    )


def _request(
    label: str = "舞台.测试",
    input_message: str = "p",
    **kwargs: object,
) -> ChatCompletionRequest:
    return ChatCompletionRequest(
        label=label,
        input_message=input_message,
        messages=[SystemMessage(content="SYS")],
        **kwargs,  # type: ignore[arg-type]
    )


def _load_all(directory: Path) -> Iterator[LlmCallRecord]:
    for path in sorted(directory.rglob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                yield LlmCallRecord.model_validate_json(line)


###############################################################################################################
# get_buffer_string（保留原有护栏）
###############################################################################################################
def test_buffer_omits_tool_calls_by_default() -> None:
    text = get_buffer_string([_ai_with_tool_call()])
    assert "[tool_calls]" not in text
    assert "get_entity_stats" not in text


def test_buffer_renders_tool_calls_when_enabled() -> None:
    text = get_buffer_string([_ai_with_tool_call()], render_tool_calls=True)
    assert "[tool_calls]" in text
    assert "get_entity_stats" in text
    assert '{"entity_name": "角色.无名"}' in text


###############################################################################################################
# 写入
###############################################################################################################
def test_records_messages_response_and_usage(calls_dir: Path) -> None:
    request = _request(input_message="请描述环境")
    result = ChatCompletionResult(
        request=request,
        ai_message=AIMessage(content="洞顶低矮"),
        finish_reason="stop",
        usage=Usage(
            prompt_tokens=3,
            completion_tokens=4,
            total_tokens=7,
            prompt_cache_hit_tokens=0,
            prompt_cache_miss_tokens=3,
        ),
        elapsed_seconds=0.25,
    )

    request_id = record_llm_call(request, result)

    assert request_id is not None
    records = list(_load_all(calls_dir))
    assert len(records) == 1
    record = records[0]
    assert record.request_id == request_id
    assert record.label == "舞台.测试"
    assert [m["type"] for m in record.messages] == ["system", "human"]
    assert record.messages[1]["content"] == "请描述环境"
    assert record.response["ai_message"]["content"] == "洞顶低矮"
    assert record.response["finish_reason"] == "stop"
    assert record.usage is not None
    assert record.usage["total_tokens"] == 7
    assert record.elapsed_ms == 250
    assert record.context_digest


def test_continuation_request_has_no_phantom_human_message(calls_dir: Path) -> None:
    request = _request(input_message="", tools=[_dummy_tool()])
    result = ChatCompletionResult(request=request, ai_message=_ai_with_tool_call())

    record_llm_call(request, result)

    record = next(_load_all(calls_dir))
    assert [m["type"] for m in record.messages] == ["system"]
    tool_calls = record.response["ai_message"]["additional_kwargs"]["tool_calls"]
    assert tool_calls[0]["function"]["name"] == "get_entity_stats"


def test_failure_record_contains_error(calls_dir: Path) -> None:
    request = _request()
    result = ChatCompletionResult(
        request=request,
        error=ChatError("舞台.测试", "HTTP 500", kind="api", status_code=500),
    )

    record_llm_call(request, result)

    record = next(_load_all(calls_dir))
    assert record.response["error"]["kind"] == "api"
    assert record.response["error"]["status_code"] == 500
    assert record.response["ai_message"] is None


def test_record_disabled_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls_dir = tmp_path / "never-created"
    monkeypatch.setattr("ai_srpg.llm.call_records.LLM_CALLS_DIR", calls_dir)

    request = _request(record=False)
    record_llm_call(
        request,
        ChatCompletionResult(request=request, ai_message=AIMessage(content="x")),
    )

    assert not calls_dir.exists()


###############################################################################################################
# 进程级开关
###############################################################################################################
@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, True),
        ("1", True),
        ("true", True),
        ("TRUE", True),
        (" yes ", True),
        ("on", True),
        ("", True),
        ("0", False),
        ("false", False),
        ("FALSE", False),
        ("no", False),
        ("off", False),
    ],
)
def test_env_switch_parsing(
    monkeypatch: pytest.MonkeyPatch, raw: "str | None", expected: bool
) -> None:
    if raw is not None:
        monkeypatch.setenv(ENV_CALL_LOG_SWITCH, raw)
    assert env_allows_call_log() is expected


def test_env_switch_off_beats_request_record_true(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls_dir = tmp_path / "never-created"
    monkeypatch.setattr("ai_srpg.llm.call_records.LLM_CALLS_DIR", calls_dir)
    monkeypatch.setenv(ENV_CALL_LOG_SWITCH, "false")

    request = _request()
    result = ChatCompletionResult(request=request, ai_message=AIMessage(content="x"))

    record_llm_call(request, result)
    record_llm_call(request, result)

    assert not calls_dir.exists()
    assert importlib.import_module("ai_srpg.llm.call_records")._warned_env_suppressed


def test_env_switch_off_and_request_record_false_stay_silent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls_dir = tmp_path / "never-created"
    monkeypatch.setattr("ai_srpg.llm.call_records.LLM_CALLS_DIR", calls_dir)
    monkeypatch.setenv(ENV_CALL_LOG_SWITCH, "0")

    request = _request(record=False)
    record_llm_call(
        request,
        ChatCompletionResult(request=request, ai_message=AIMessage(content="x")),
    )

    assert not calls_dir.exists()
    assert not importlib.import_module(
        "ai_srpg.llm.call_records"
    )._warned_env_suppressed


###############################################################################################################
# 读取
###############################################################################################################
def test_iter_and_find_records(calls_dir: Path) -> None:
    for index in range(3):
        request = _request(label=f"label-{index}")
        result = ChatCompletionResult(
            request=request, ai_message=AIMessage(content=f"reply-{index}")
        )
        record_llm_call(request, result)

    records = list(iter_llm_call_records())
    assert [r.label for r in records] == ["label-2", "label-1", "label-0"]

    filtered = list(iter_llm_call_records(label="label-1"))
    assert [r.label for r in filtered] == ["label-1"]

    target = records[0]
    found = find_llm_call(target.request_id[:8])
    assert found is not None
    assert found.request_id == target.request_id
    assert find_llm_call("does-not-exist") is None


def test_build_record_is_pure(calls_dir: Path) -> None:
    request = _request()
    result = ChatCompletionResult(request=request, ai_message=AIMessage(content="x"))

    record = build_llm_call_record(request, result)

    assert record.message_count == 2
    assert record.model is None
    assert list(calls_dir.glob("*.jsonl")) == []


###############################################################################################################
# CLI：开发期检查入口
###############################################################################################################
def test_cli_lists_and_shows_record(calls_dir: Path) -> None:
    from click.testing import CliRunner

    from ai_srpg.cli.srpg_agent_game import main

    request = _request(input_message="请描述环境")
    result = ChatCompletionResult(
        request=request, ai_message=AIMessage(content="洞顶低矮")
    )
    request_id = record_llm_call(request, result)
    assert request_id is not None

    runner = CliRunner()
    listed = runner.invoke(main, ["llm-calls", "--limit", "1"])
    assert listed.exit_code == 0
    assert request_id[:8] in listed.output
    assert "舞台.测试" in listed.output

    shown = runner.invoke(main, ["llm-call", request_id[:8]])
    assert shown.exit_code == 0
    assert "请描述环境" in shown.output
    assert "洞顶低矮" in shown.output

    as_json = runner.invoke(main, ["llm-call", request_id, "--json"])
    assert as_json.exit_code == 0
    assert '"request_id"' in as_json.output


###############################################################################################################
# trace / 分析字段 / 文件切分
###############################################################################################################
def test_record_carries_trace_started_at_and_context_ratio(calls_dir: Path) -> None:
    request = _request()
    started_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    result = ChatCompletionResult(
        request=request,
        ai_message=AIMessage(content="x", context_usage_ratio=0.25),
        started_at=started_at,
    )

    with llm_call_trace(
        scope="cli",
        scope_id="test-process",
        user="alice",
        game="Game1",
        command="advance",
        snapshot_id=7,
        loop_id="L1",
        round=2,
        agent="角色.无名",
        entity="角色.无名",
    ):
        record_llm_call(request, result)

    record = next(_load_all(calls_dir))
    assert record.started_at == started_at
    assert record.context_usage_ratio == 0.25
    assert record.trace.user == "alice"
    assert record.trace.game == "Game1"
    assert record.trace.command == "advance"
    assert record.trace.snapshot_id == 7
    assert record.trace.loop_id == "L1"
    assert record.trace.round == 2
    assert record.trace.agent == "角色.无名"
    assert list((calls_dir / "cli-test-process").glob("*.jsonl"))


def test_record_without_started_at_uses_elapsed(calls_dir: Path) -> None:
    request = _request()
    result = ChatCompletionResult(
        request=request,
        ai_message=AIMessage(content="x"),
        elapsed_seconds=1.5,
    )

    record_llm_call(request, result)

    record = next(_load_all(calls_dir))
    assert record.started_at is not None
    assert (record.created_at - record.started_at).total_seconds() == pytest.approx(
        1.5, abs=0.1
    )


def test_iter_filters_trace_fields(calls_dir: Path) -> None:
    for user, game, command in (
        ("alice", "Game1", "advance"),
        ("alice", "Game2", "advance"),
        ("bob", "Game1", "stages"),
    ):
        request = _request(label=f"{user}-{game}-{command}")
        result = ChatCompletionResult(
            request=request, ai_message=AIMessage(content="x")
        )
        with llm_call_trace(user=user, game=game, command=command, scope="cli"):
            record_llm_call(request, result)

    assert [r.label for r in iter_llm_call_records(user="alice")] == [
        "alice-Game2-advance",
        "alice-Game1-advance",
    ]
    assert [r.label for r in iter_llm_call_records(game="Game1", command="stages")] == [
        "bob-Game1-stages"
    ]
    assert list(iter_llm_call_records(user="nobody")) == []


def test_cli_filters_and_json(calls_dir: Path) -> None:
    from click.testing import CliRunner

    from ai_srpg.cli.srpg_agent_game import main

    request = _request()
    result = ChatCompletionResult(request=request, ai_message=AIMessage(content="x"))
    with llm_call_trace(user="alice", game="Game1", command="advance", scope="cli"):
        request_id = record_llm_call(request, result)

    runner = CliRunner()
    listed = runner.invoke(
        main,
        ["llm-calls", "--user", "alice", "--game", "Game1", "--json"],
    )
    assert listed.exit_code == 0
    assert request_id is not None
    assert request_id in listed.output

    empty = runner.invoke(main, ["llm-calls", "--user", "nobody"])
    assert empty.exit_code == 0
    assert "没有 llm call 记录" in empty.output


def test_default_scope_is_cli_with_pid(calls_dir: Path) -> None:
    request = _request()
    result = ChatCompletionResult(request=request, ai_message=AIMessage(content="x"))

    record_llm_call(request, result)

    record = next(_load_all(calls_dir))
    assert record.trace.scope == "cli"
    assert record.trace.scope_id
    assert (calls_dir / f"cli-{record.trace.scope_id}").is_dir()


def test_iter_filters_by_time(calls_dir: Path) -> None:
    request = _request()
    result = ChatCompletionResult(request=request, ai_message=AIMessage(content="x"))
    record_llm_call(request, result)

    now = datetime.now(timezone.utc)
    assert len(list(iter_llm_call_records(since=now - timedelta(days=1)))) == 1
    assert list(iter_llm_call_records(until=now - timedelta(days=1))) == []
