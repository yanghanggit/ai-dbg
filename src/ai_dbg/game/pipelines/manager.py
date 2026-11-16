from typing import Optional

from ...entitas import ProcessorPipeline
from ...entitas.processor_interfaces import ProcessorObserver


###################################################################################################################################################################
class RPGGameProcessPipeline(ProcessorPipeline):
    """RPG 游戏流程管道，管理处理器的执行和生命周期。"""

    ###################################################################################################################################################################
    async def process(self, observer: Optional[ProcessorObserver]) -> None:
        """执行管道中的所有处理器，然后清理临时状态。

        observer 由调用方显式传入；不传观测器时显式传 ``None``，
        pipeline 不会从任何全局上下文偷偷取默认值。
        """
        await self.execute(observer)
        self.cleanup()

    ###############################################################################################################################################
    def shutdown(self) -> None:
        """关闭管道并清理资源。"""
        self.tear_down()
        self.clear_reactive_processors()
