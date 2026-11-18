"""Pipeline 运行辅助：在 ProcessorPipeline 之上补两个生命周期约定。

`ProcessorPipeline` 只是 processor 容器；这里定义「一次 pass 怎么运行、怎么关闭」，
不引入新的 pipeline 类型，调用方直接持有并传入 `ProcessorPipeline`。
"""

from typing import Optional

from loguru import logger

from ...entitas import ProcessorPipeline
from ...entitas.processor_interfaces import ProcessorObserver


###################################################################################################################################################################
async def process_pipeline(
    pipeline: ProcessorPipeline, observer: Optional[ProcessorObserver]
) -> None:
    """执行一次 pass：execute 之后必定 cleanup。

    cleanup 是 pass 的收尾阶段，必须在 execute 抛异常时也执行，避免临时动作组件
    残留在半完成的世界里。失败路径的 cleanup 异常只记录，不覆盖原始 processor
    异常。observer 由调用方显式传入；不传观测器时显式传 ``None``，pipeline 不会
    从任何全局上下文偷偷取默认值。
    """
    try:
        await pipeline.execute(observer)
    except BaseException:
        try:
            pipeline.cleanup()
        except Exception:
            logger.exception("pipeline cleanup failed after execute error")
        raise
    else:
        pipeline.cleanup()


###############################################################################################################################################
def close_pipeline(pipeline: ProcessorPipeline) -> None:
    """关闭 pipeline：tear_down 并清空反应式处理器已收集的实体。"""
    pipeline.tear_down()
    pipeline.clear_reactive_processors()
