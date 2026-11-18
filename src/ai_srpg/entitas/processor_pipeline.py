"""The processor pipeline: a concrete container that runs processors in order."""

import time
from typing import List, Optional, Union, override

from .exceptions import StopPipeline
from .pass_result import PassResult
from .processor_interfaces import (
    CleanupProcessor,
    ExecuteProcessor,
    InitializeProcessor,
    ProcessorObserver,
    TearDownProcessor,
)
from .reactive_processor import ReactiveProcessor


class ProcessorPipeline(
    InitializeProcessor, ExecuteProcessor, CleanupProcessor, TearDownProcessor
):
    """A container for managing multiple processors in an organized pipeline.

    The ProcessorPipeline class allows you to group related processors together
    and execute them in the correct order: Initialize -> Execute -> Cleanup -> TearDown.
    It also supports nested pipelines and reactive processor management.
    """

    def __init__(self) -> None:
        """Initializes an empty processor pipeline."""
        self._initialize_processors: List[InitializeProcessor] = []
        self._execute_processors: List[ExecuteProcessor] = []
        self._cleanup_processors: List[CleanupProcessor] = []
        self._tear_down_processors: List[TearDownProcessor] = []
        self._last_pass: PassResult = PassResult()

    ###########################################################################
    @property
    def last_pass(self) -> PassResult:
        """最近一次 ``execute()`` 的调度结果。"""
        return self._last_pass

    def add(
        self,
        processor: Union[
            InitializeProcessor, ExecuteProcessor, CleanupProcessor, TearDownProcessor
        ],
    ) -> None:
        """Adds a processor to the appropriate execution lists.

        A processor can implement multiple interfaces and will be added
        to all appropriate lists.

        :param processor: The processor to add to the pipeline
        """
        if isinstance(processor, InitializeProcessor):
            self._initialize_processors.append(processor)

        if isinstance(processor, ExecuteProcessor):
            self._execute_processors.append(processor)

        if isinstance(processor, CleanupProcessor):
            self._cleanup_processors.append(processor)

        if isinstance(processor, TearDownProcessor):
            self._tear_down_processors.append(processor)

    @override
    async def initialize(self, observer: Optional[ProcessorObserver] = None) -> None:
        """Executes all initialize processors in the order they were added.

        任何异常都原样上抛；``StopPipeline`` 只作为显式的启动中止信号传递，
        同样不计为失败。
        """
        for processor in self._initialize_processors:
            system = type(processor).__name__
            if observer is not None:
                observer.on_processor_started(system)
            started = time.perf_counter()

            try:
                await processor.initialize()
            except StopPipeline:
                raise
            except Exception as exc:
                duration_ms = (time.perf_counter() - started) * 1000.0
                if observer is not None:
                    observer.on_processor_failed(system, exc, duration_ms)
                raise
            else:
                if observer is not None:
                    observer.on_processor_finished(
                        system, (time.perf_counter() - started) * 1000.0
                    )

    @override
    async def execute(self, observer: Optional[ProcessorObserver] = None) -> None:
        """Executes all execute processors in the order they were added.

        普通异常不在这里处理，原样上抛；``StopPipeline`` 是唯一的提前结束
        信号，记录被跳过的 processor 后继续向上传递，由应用边界消费。
        """
        systems = [type(processor).__name__ for processor in self._execute_processors]
        ran: List[str] = []

        for index, processor in enumerate(self._execute_processors):
            system = systems[index]
            if observer is not None:
                observer.on_processor_started(system)
            started = time.perf_counter()

            try:
                await processor.execute()
            except StopPipeline:
                self._last_pass = PassResult(
                    ran=tuple(ran),
                    skipped=tuple(systems[index + 1 :]),
                    aborted_by=system,
                )
                raise
            except Exception as exc:
                duration_ms = (time.perf_counter() - started) * 1000.0
                if observer is not None:
                    observer.on_processor_failed(system, exc, duration_ms)
                raise
            else:
                ran.append(system)
                if observer is not None:
                    observer.on_processor_finished(
                        system, (time.perf_counter() - started) * 1000.0
                    )

        self._last_pass = PassResult(ran=tuple(ran))

    @override
    def cleanup(self) -> None:
        """Executes all cleanup processors in the order they were added."""
        for processor in self._cleanup_processors:
            processor.cleanup()

    @override
    def tear_down(self, observer: Optional[ProcessorObserver] = None) -> None:
        """Executes all tear down processors in the order they were added.

        任何异常都原样上抛；``StopPipeline`` 只作为显式的关闭中止信号传递，
        同样不计为失败。
        """
        for processor in self._tear_down_processors:
            system = type(processor).__name__
            if observer is not None:
                observer.on_processor_started(system)
            started = time.perf_counter()

            try:
                processor.tear_down()
            except StopPipeline:
                raise
            except Exception as exc:
                duration_ms = (time.perf_counter() - started) * 1000.0
                if observer is not None:
                    observer.on_processor_failed(system, exc, duration_ms)
                raise
            else:
                if observer is not None:
                    observer.on_processor_finished(
                        system, (time.perf_counter() - started) * 1000.0
                    )

    def activate_reactive_processors(self) -> None:
        """Activates all reactive processors in this pipeline and nested pipelines."""
        for processor in self._execute_processors:
            if isinstance(processor, ReactiveProcessor):
                processor.activate()

            if isinstance(processor, ProcessorPipeline):
                processor.activate_reactive_processors()

    def deactivate_reactive_processors(self) -> None:
        """Deactivates all reactive processors in this pipeline and nested pipelines."""
        for processor in self._execute_processors:
            if isinstance(processor, ReactiveProcessor):
                processor.deactivate()

            if isinstance(processor, ProcessorPipeline):
                processor.deactivate_reactive_processors()

    def clear_reactive_processors(self) -> None:
        """Clears all collected entities from reactive processors in this pipeline and nested pipelines."""
        for processor in self._execute_processors:
            if isinstance(processor, ReactiveProcessor):
                processor.clear()

            if isinstance(processor, ProcessorPipeline):
                processor.clear_reactive_processors()
