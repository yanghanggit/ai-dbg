"""Pipeline 运行辅助（process_pipeline / close_pipeline）的生命周期测试。"""

from typing import Dict, List, Optional

import pytest

from ai_srpg.entitas import (
    CleanupProcessor,
    Entity,
    ErrorPolicy,
    ExecuteProcessor,
    GroupEvent,
    Matcher,
    ProcessorPipeline,
    ReactiveProcessor,
    StopPipeline,
    TearDownProcessor,
)
from ai_srpg.game.pipelines import close_pipeline, process_pipeline


class _RecordingExecute(ExecuteProcessor):
    def __init__(self, events: List[str], error: Exception | None = None) -> None:
        self._events = events
        self._error = error

    async def execute(self) -> None:
        self._events.append("execute")
        if self._error is not None:
            raise self._error


class _RecordingCleanup(CleanupProcessor):
    def __init__(self, events: List[str]) -> None:
        self._events = events

    def cleanup(self) -> None:
        self._events.append("cleanup")


class _FailingCleanup(CleanupProcessor):
    def cleanup(self) -> None:
        raise RuntimeError("cleanup boom")


async def test_process_runs_cleanup_on_success() -> None:
    events: List[str] = []
    pipeline = ProcessorPipeline()
    pipeline.add(_RecordingExecute(events))
    pipeline.add(_RecordingCleanup(events))

    await process_pipeline(pipeline, None)

    assert events == ["execute", "cleanup"]


async def test_process_runs_cleanup_when_execute_raises() -> None:
    events: List[str] = []
    pipeline = ProcessorPipeline()
    pipeline.add(_RecordingExecute(events, RuntimeError("execute boom")))
    pipeline.add(_RecordingCleanup(events))

    with pytest.raises(RuntimeError, match="execute boom"):
        await process_pipeline(pipeline, None)

    assert events == ["execute", "cleanup"]


async def test_process_preserves_execute_error_when_cleanup_fails() -> None:
    events: List[str] = []
    pipeline = ProcessorPipeline()
    pipeline.add(_RecordingExecute(events, RuntimeError("execute boom")))
    pipeline.add(_FailingCleanup())

    with pytest.raises(RuntimeError, match="execute boom"):
        await process_pipeline(pipeline, None)

    assert events == ["execute"]


def test_close_pipeline_tears_down() -> None:
    events: List[str] = []

    class _RecordingTearDown(TearDownProcessor):
        def tear_down(self) -> None:
            events.append("teardown")

    pipeline = ProcessorPipeline()
    pipeline.add(_RecordingTearDown())

    close_pipeline(pipeline)

    assert events == ["teardown"]


class _Step(ExecuteProcessor):
    """可配置的 processor：正常返回、抛错（带策略）或提前结束。"""

    def __init__(
        self,
        events: List[str],
        *,
        error: Optional[Exception] = None,
        policy: Optional[ErrorPolicy] = None,
        stop: bool = False,
    ) -> None:
        self._events = events
        self._error = error
        self._stop = stop
        if policy is not None:
            self.error_policy = policy

    async def execute(self) -> None:
        self._events.append("step")
        if self._stop:
            raise StopPipeline("stop requested")
        if self._error is not None:
            raise self._error


async def test_propagate_policy_interrupts_pass() -> None:
    events: List[str] = []
    pipeline = ProcessorPipeline()
    pipeline.add(_Step(events, error=RuntimeError("boom")))
    pipeline.add(_Step(events))

    with pytest.raises(RuntimeError, match="boom"):
        await process_pipeline(pipeline, None)

    result = pipeline.last_pass
    assert events == ["step"]
    assert result.interrupted
    assert not result.completed
    assert result.skipped == ("_Step",)
    assert [f.system for f in result.failures] == ["_Step"]
    assert str(result.failures[0].error) == "boom"


async def test_continue_policy_records_failure_and_keeps_going() -> None:
    events: List[str] = []
    pipeline = ProcessorPipeline()
    pipeline.add(
        _Step(events, error=RuntimeError("local"), policy=ErrorPolicy.CONTINUE)
    )
    pipeline.add(_Step(events))

    result = await process_pipeline(pipeline, None)

    assert events == ["step", "step"]
    assert result.completed
    assert not result.interrupted
    assert result.skipped == ()
    assert str(result.failures[0].error) == "local"


async def test_stop_pipeline_aborts_without_raising() -> None:
    events: List[str] = []
    pipeline = ProcessorPipeline()
    pipeline.add(_Step(events))
    pipeline.add(_Step(events, stop=True))
    pipeline.add(_Step(events))

    result = await process_pipeline(pipeline, None)

    assert events == ["step", "step"]
    assert result.aborted_by == "_Step"
    assert result.skipped == ("_Step",)
    assert not result.completed
    assert not result.interrupted


async def test_nested_pipeline_abort_propagates_to_parent() -> None:
    events: List[str] = []
    child = ProcessorPipeline()
    child.add(_Step(events, stop=True))
    child.add(_Step(events))

    parent = ProcessorPipeline()
    parent.add(child)
    parent.add(_Step(events))

    result = await process_pipeline(parent, None)

    assert events == ["step"]
    assert child.last_pass.aborted_by == "_Step"
    assert parent.last_pass.aborted_by == "ProcessorPipeline"
    assert parent.last_pass.skipped == ("_Step",)
    assert result is parent.last_pass


class _FakeReactive(ReactiveProcessor):
    """只关心 clear() 是否被调用的反应式 processor。"""

    def __init__(self, events: List[str]) -> None:
        self._events = events

    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {}

    def filter(self, entity: Entity) -> bool:
        return True

    async def react(self, entities: List[Entity]) -> None:
        return None

    def clear(self) -> None:
        self._events.append("clear")


def test_close_pipeline_clears_reactive_processors_even_if_teardown_fails() -> None:
    events: List[str] = []

    class _FailingTearDown(TearDownProcessor):
        def tear_down(self) -> None:
            raise RuntimeError("teardown boom")

    pipeline = ProcessorPipeline()
    pipeline.add(_FakeReactive(events))
    pipeline.add(_FailingTearDown())

    with pytest.raises(RuntimeError, match="teardown boom"):
        close_pipeline(pipeline)

    assert events == ["clear"]
