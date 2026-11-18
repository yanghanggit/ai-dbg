"""Processor 接口契约测试：抽象方法、阶段形态与多接口组合。"""

import inspect
from typing import List

import pytest

from ai_srpg.entitas import (
    CleanupProcessor,
    ExecuteProcessor,
    InitializeProcessor,
    ProcessorObserver,
    TearDownProcessor,
)


class _AllPhases(
    InitializeProcessor, ExecuteProcessor, CleanupProcessor, TearDownProcessor
):
    def __init__(self) -> None:
        self.calls: List[str] = []

    async def initialize(self) -> None:
        self.calls.append("initialize")

    async def execute(self) -> None:
        self.calls.append("execute")

    def cleanup(self) -> None:
        self.calls.append("cleanup")

    def tear_down(self) -> None:
        self.calls.append("tear_down")


def test_abstract_methods_are_exactly_the_lifecycle_hooks() -> None:
    assert InitializeProcessor.__abstractmethods__ == frozenset({"initialize"})
    assert ExecuteProcessor.__abstractmethods__ == frozenset({"execute"})
    assert CleanupProcessor.__abstractmethods__ == frozenset({"cleanup"})
    assert TearDownProcessor.__abstractmethods__ == frozenset({"tear_down"})


@pytest.mark.parametrize(
    "processor",
    [InitializeProcessor, ExecuteProcessor, CleanupProcessor, TearDownProcessor],
)
def test_abstract_processors_cannot_be_instantiated(processor: type) -> None:
    with pytest.raises(TypeError):
        processor()


def test_async_and_sync_hooks_have_expected_shape() -> None:
    assert inspect.iscoroutinefunction(InitializeProcessor.initialize)
    assert inspect.iscoroutinefunction(ExecuteProcessor.execute)
    assert not inspect.iscoroutinefunction(CleanupProcessor.cleanup)
    assert not inspect.iscoroutinefunction(TearDownProcessor.tear_down)


async def test_multi_interface_processor_exposes_all_hooks() -> None:
    processor = _AllPhases()

    await processor.initialize()
    await processor.execute()
    processor.cleanup()
    processor.tear_down()

    assert processor.calls == ["initialize", "execute", "cleanup", "tear_down"]


def test_no_error_policy_on_interfaces() -> None:
    """错误策略已收敛到上层：接口只保留生命周期。"""
    for processor in (
        InitializeProcessor,
        ExecuteProcessor,
        CleanupProcessor,
        TearDownProcessor,
    ):
        assert not hasattr(processor, "error_policy")


def test_processor_observer_is_a_protocol() -> None:
    assert getattr(ProcessorObserver, "_is_protocol", False) is True


def test_processor_observer_can_be_implemented_structurally() -> None:
    class _Observer:
        def __init__(self) -> None:
            self.started: List[str] = []

        def on_processor_started(self, system: str) -> None:
            self.started.append(system)

        def on_processor_finished(self, system: str, duration_ms: float) -> None:
            self.started.append(system)

        def on_processor_failed(
            self, system: str, error: BaseException, duration_ms: float
        ) -> None:
            self.started.append(system)

    observer: ProcessorObserver = _Observer()
    observer.on_processor_started("Demo")

    assert getattr(observer, "started") == ["Demo"]
