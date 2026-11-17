"""RPGGameProcessPipeline 的 execute/cleanup 生命周期测试。"""

from typing import List

import pytest

from ai_dbg.entitas import CleanupProcessor, ExecuteProcessor
from ai_dbg.game.pipelines.manager import RPGGameProcessPipeline


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
    pipeline = RPGGameProcessPipeline()
    pipeline.add(_RecordingExecute(events))
    pipeline.add(_RecordingCleanup(events))

    await pipeline.process(None)

    assert events == ["execute", "cleanup"]


async def test_process_runs_cleanup_when_execute_raises() -> None:
    events: List[str] = []
    pipeline = RPGGameProcessPipeline()
    pipeline.add(_RecordingExecute(events, RuntimeError("execute boom")))
    pipeline.add(_RecordingCleanup(events))

    with pytest.raises(RuntimeError, match="execute boom"):
        await pipeline.process(None)

    assert events == ["execute", "cleanup"]


async def test_process_preserves_execute_error_when_cleanup_fails() -> None:
    events: List[str] = []
    pipeline = RPGGameProcessPipeline()
    pipeline.add(_RecordingExecute(events, RuntimeError("execute boom")))
    pipeline.add(_FailingCleanup())

    with pytest.raises(RuntimeError, match="execute boom"):
        await pipeline.process(None)

    assert events == ["execute"]
