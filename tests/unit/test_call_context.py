"""LLM 调用 trace contextvar：合并、覆盖与恢复。"""

from ai_srpg.llm.call_context import current_llm_trace, llm_call_trace


def test_default_trace_is_empty() -> None:
    trace = current_llm_trace()
    assert trace.scope == ""
    assert trace.user == ""
    assert trace.round == 0
    assert trace.snapshot_id is None


def test_trace_is_merged_and_reset() -> None:
    with llm_call_trace(scope="cli", user="alice", game="Game1"):
        assert current_llm_trace().user == "alice"

        with llm_call_trace(command="advance", round=2):
            trace = current_llm_trace()
            assert trace.scope == "cli"
            assert trace.user == "alice"
            assert trace.command == "advance"
            assert trace.round == 2

        assert current_llm_trace().command == ""
        assert current_llm_trace().round == 0

    assert current_llm_trace().user == ""
    assert current_llm_trace().scope == ""


def test_round_is_zero_based_default_and_optional_fields_are_ignored() -> None:
    with llm_call_trace(round=0, snapshot_id=None, loop_id=None):
        trace = current_llm_trace()
        assert trace.round == 0
        assert trace.snapshot_id is None
        assert trace.loop_id == ""
