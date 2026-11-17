from typing import Optional

from loguru import logger

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

        cleanup 是 pass 的收尾阶段，必须在 execute 抛异常时也执行，避免
        临时动作组件残留在半完成的世界里。失败路径的 cleanup 异常只记录，
        不覆盖原始 system 异常。
        """
        try:
            await self.execute(observer)
        except BaseException:
            try:
                self.cleanup()
            except Exception:
                logger.exception("pipeline cleanup failed after execute error")
            raise
        else:
            self.cleanup()

    ###############################################################################################################################################
    def shutdown(self) -> None:
        """关闭管道并清理资源。"""
        self.tear_down()
        self.clear_reactive_processors()
