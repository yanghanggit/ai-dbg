"""initialize / tear_down 阶段的 observer 与失败策略测试。"""

from typing import List, Optional, Tuple

import pytest

from ai_srpg.entitas import (
    ErrorPolicy,
    InitializeProcessor,
    ProcessorObserver,
    ProcessorPipeline,
    StopPipeline,
    TearDownProcessor,
)


class _Observer(ProcessorObserver):
    def __init__(self) -> None:
        self.events: List[Tuple[str, str]] = []
        self.failures: List[Tuple[str, BaseException]] = []

    def on_processor_started(self, system: str) -> None:
        self.events.append(("start", system))

    def on_processor_finished(self, system: str, duration_ms: float) -> None:
        assert duration_ms >= 0.0
        self.events.append(("finish", system))

    def on_processor_failed(
        self, system: str, error: BaseException, duration_ms: float
    ) -> None:
        assert duration_ms >= 0.0
        self.failures.append((system, error))
        self.events.append(("fail", system))


class _Init(InitializeProcessor):
    def __init__(
        self,
        log: List[str],
        *,
        error: Optional[Exception] = None,
        policy: Optional[ErrorPolicy] = None,
    ) -> None:
        self._log = log
        self._error = error
        if policy is not None:
            self.error_policy = policy

    async def initialize(self) -> None:
        self._log.append("init")
        if self._error is not None:
            raise self._error


class _TearDown(TearDownProcessor):
    def __init__(
        self,
        log: List[str],
        *,
        error: Optional[Exception] = None,
        policy: Optional[ErrorPolicy] = None,
    ) -> None:
        self._log = log
        self._error = error
        if policy is not None:
            self.error_policy = policy

    def tear_down(self) -> None:
        self._log.append("tear_down")
        if self._error is not None:
            raise self._error


async def test_initialize_notifies_observer() -> None:
    observer = _Observer()
    pipeline = ProcessorPipeline()
    pipeline.add(_Init([]))
    pipeline.add(_Init([]))

    await pipeline.initialize(observer)

    assert observer.events == [
        ("start", "_Init"),
        ("finish", "_Init"),
        ("start", "_Init"),
        ("finish", "_Init"),
    ]
    assert observer.failures == []


async def test_initialize_propagate_stops_remaining() -> None:
    log: List[str] = []
    observer = _Observer()
    pipeline = ProcessorPipeline()
    pipeline.add(_Init(log, error=RuntimeError("init boom")))
    pipeline.add(_Init(log))

    with pytest.raises(RuntimeError, match="init boom"):
        await pipeline.initialize(observer)

    assert log == ["init"]
    assert observer.events == [("start", "_Init"), ("fail", "_Init")]
    assert str(observer.failures[0][1]) == "init boom"


async def test_initialize_continue_policy_keeps_going() -> None:
    log: List[str] = []
    observer = _Observer()
    pipeline = ProcessorPipeline()
    pipeline.add(_Init(log, error=RuntimeError("local"), policy=ErrorPolicy.CONTINUE))
    pipeline.add(_Init(log))

    await pipeline.initialize(observer)

    assert log == ["init", "init"]
    assert observer.events == [
        ("start", "_Init"),
        ("fail", "_Init"),
        ("start", "_Init"),
        ("finish", "_Init"),
    ]


async def test_tear_down_notifies_observer_and_continues_on_policy() -> None:
    log: List[str] = []
    observer = _Observer()
    pipeline = ProcessorPipeline()
    pipeline.add(
        _TearDown(log, error=RuntimeError("local"), policy=ErrorPolicy.CONTINUE)
    )
    pipeline.add(_TearDown(log))

    pipeline.tear_down(observer)

    assert log == ["tear_down", "tear_down"]
    assert observer.events == [
        ("start", "_TearDown"),
        ("fail", "_TearDown"),
        ("start", "_TearDown"),
        ("finish", "_TearDown"),
    ]


async def test_tear_down_propagate_stops_remaining() -> None:
    log: List[str] = []
    observer = _Observer()
    pipeline = ProcessorPipeline()
    pipeline.add(_TearDown(log, error=RuntimeError("teardown boom")))
    pipeline.add(_TearDown(log))

    with pytest.raises(RuntimeError, match="teardown boom"):
        pipeline.tear_down(observer)

    assert log == ["tear_down"]
    assert observer.events == [("start", "_TearDown"), ("fail", "_TearDown")]


async def test_stop_pipeline_is_not_a_failure() -> None:
    class _StopInit(InitializeProcessor):
        async def initialize(self) -> None:
            raise StopPipeline("startup aborted")

    observer = _Observer()
    pipeline = ProcessorPipeline()
    pipeline.add(_StopInit())

    with pytest.raises(StopPipeline, match="startup aborted"):
        await pipeline.initialize(observer)

    assert observer.events == [("start", "_StopInit")]
    assert observer.failures == []
