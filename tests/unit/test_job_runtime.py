"""Job 执行事件与 pipeline observer 的单测。"""

from typing import List

import pytest

from ai_dbg.entitas import ProcessorPipeline
from ai_dbg.entitas.processor_interfaces import ExecuteProcessor
from ai_dbg.models import JobEvent
from ai_dbg.services.job_runtime import JobRecorder, JobRun


class MemoryStore:
    def __init__(self) -> None:
        self.events: List[JobEvent] = []

    def append(self, event: JobEvent) -> None:
        self.events.append(event)


class _System(ExecuteProcessor):
    def __init__(self, name: str, error: Exception | None = None) -> None:
        self.name = name
        self.error = error

    async def execute(self) -> None:
        if self.error is not None:
            raise self.error


class FirstSystem(_System):
    pass


class SecondSystem(_System):
    pass


class BrokenSystem(_System):
    pass


class NeverSystem(_System):
    pass


def _kinds(store: MemoryStore) -> List[str]:
    return [event.kind for event in store.events]


def test_recorder_records_system_lifecycle() -> None:
    store = MemoryStore()
    recorder = JobRecorder(7, action="play_cards", store=store)

    recorder.started()
    recorder.on_processor_started("A")
    recorder.on_processor_finished("A", 1.25)
    recorder.succeeded()

    assert _kinds(store) == [
        "job_started",
        "system_started",
        "system_finished",
        "job_succeeded",
    ]
    assert store.events[0].payload["action"] == "play_cards"
    assert store.events[2].payload["duration_ms"] == 1.25


def test_recorder_records_failed_system_and_job() -> None:
    store = MemoryStore()
    recorder = JobRecorder(7, store=store)
    error = ValueError("boom")

    recorder.started()
    recorder.on_processor_started("BrokenSystem")
    recorder.on_processor_failed("BrokenSystem", error, 2.0)
    recorder.failed(error, system="BrokenSystem")

    assert _kinds(store)[-2:] == ["system_failed", "job_failed"]
    assert store.events[-1].message == "boom"
    assert store.events[-1].system == "BrokenSystem"


async def test_pipeline_observer_receives_each_system() -> None:
    pipeline = ProcessorPipeline()
    pipeline.add(FirstSystem("first"))
    pipeline.add(SecondSystem("second"))
    store = MemoryStore()
    recorder = JobRecorder(1, store=store)

    await pipeline.execute(recorder)

    started = [e.system for e in store.events if e.kind == "system_started"]
    finished = [e.system for e in store.events if e.kind == "system_finished"]
    assert started == ["FirstSystem", "SecondSystem"]
    assert finished == ["FirstSystem", "SecondSystem"]


async def test_pipeline_observer_stops_on_failure() -> None:
    pipeline = ProcessorPipeline()
    pipeline.add(FirstSystem("ok"))
    pipeline.add(BrokenSystem("broken", ValueError("boom")))
    pipeline.add(NeverSystem("never"))
    store = MemoryStore()
    recorder = JobRecorder(1, store=store)

    with pytest.raises(ValueError, match="boom"):
        await pipeline.execute(recorder)

    assert [e.system for e in store.events if e.kind == "system_started"] == [
        "FirstSystem",
        "BrokenSystem",
    ]
    assert [e.system for e in store.events if e.kind == "system_failed"] == [
        "BrokenSystem"
    ]


async def test_job_run_records_success_without_room() -> None:
    store = MemoryStore()
    async with JobRun(9, action="test", store=store):
        pass

    assert _kinds(store) == ["job_started", "job_succeeded"]


async def test_job_run_records_failure_without_room() -> None:
    store = MemoryStore()
    with pytest.raises(RuntimeError, match="boom"):
        async with JobRun(9, action="test", store=store):
            raise RuntimeError("boom")

    assert _kinds(store) == ["job_started", "job_failed"]
    assert store.events[-1].message == "boom"
