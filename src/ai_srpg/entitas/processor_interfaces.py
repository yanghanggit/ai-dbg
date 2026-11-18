"""Processor contracts (abstract interfaces) for the processor pipeline.

These are pure interfaces: they define the lifecycle hooks a processor may
implement. A single object may implement several of them; see
:class:`~ai_srpg.entitas.processor_pipeline.ProcessorPipeline` for the composite
that runs them in order.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Protocol


class ErrorPolicy(Enum):
    """What the pipeline does when a processor raises."""

    PROPAGATE = "propagate"
    CONTINUE = "continue"


class InitializeProcessor(ABC):
    """Base class for processors that run once during pipeline initialization.

    Initialize processors are executed when the processing pipeline starts up.
    Use this for one-time setup operations like loading resources or
    initializing system state.
    """

    #: 失败后的调度策略；默认传播：初始化是启动顺序的一部分，失败后后续步骤不应继续。
    error_policy: ErrorPolicy = ErrorPolicy.PROPAGATE

    @abstractmethod
    async def initialize(self) -> None:
        """Performs initialization logic.

        This method is called once when the processing pipeline starts.
        """


class ProcessorObserver(Protocol):
    """可选观测器：由 pipeline 在 system 边界调用。"""

    def on_processor_started(self, system: str) -> None:
        """开始执行某个 system。"""

    def on_processor_finished(self, system: str, duration_ms: float) -> None:
        """某个 system 正常结束。"""

    def on_processor_failed(
        self, system: str, error: BaseException, duration_ms: float
    ) -> None:
        """某个 system 抛异常。"""


class ExecuteProcessor(ABC):
    """Base class for processors that run every frame/cycle.

    Execute processors contain the main game logic and are called
    repeatedly during the game loop.
    """

    #: 失败后的调度策略，由组装方按 processor 在 pipeline 中的位置声明。
    #: 默认传播：pipeline 的意义就是顺序依赖，某一步没有完成时序列不再可信。
    error_policy: ErrorPolicy = ErrorPolicy.PROPAGATE

    @abstractmethod
    async def execute(self) -> None:
        """Performs the main processing logic.

        This method is called every frame/cycle of the game loop.
        """


class CleanupProcessor(ABC):
    """Base class for processors that run cleanup operations after each cycle.

    Cleanup processors are executed after all execute processors have run.
    Use this for operations like removing expired entities or cleaning up
    temporary state.
    """

    @abstractmethod
    def cleanup(self) -> None:
        """Performs cleanup operations.

        This method is called after each execution cycle to clean up
        temporary state or perform maintenance tasks.
        """


class TearDownProcessor(ABC):
    """Base class for processors that run during application shutdown.

    TearDown processors are executed when the application or game is
    shutting down. Use this for final cleanup operations like saving
    data or releasing resources.
    """

    #: 失败后的调度策略；默认传播：关闭顺序同样可能相互依赖，失败应显式暴露。
    error_policy: ErrorPolicy = ErrorPolicy.PROPAGATE

    @abstractmethod
    def tear_down(self) -> None:
        """Performs final cleanup during shutdown.

        This method is called once when the application is shutting down.
        """
