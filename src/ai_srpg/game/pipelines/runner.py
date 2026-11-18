"""Pipeline 运行辅助：在 ProcessorPipeline 之上补两个生命周期约定。

`ProcessorPipeline` 只是 processor 容器；这里定义「一次 pass 怎么运行、怎么关闭」，
不引入新的 pipeline 类型，调用方直接持有并传入 `ProcessorPipeline`。
"""

from typing import Optional

from loguru import logger

from ...entitas import ProcessorPipeline
from ...entitas.exceptions import StopPipeline
from ...entitas.pass_result import PassResult
from ...entitas.processor_interfaces import ProcessorObserver


###################################################################################################################################################################
async def process_pipeline(
    pipeline: ProcessorPipeline, observer: Optional[ProcessorObserver]
) -> PassResult:
    """执行一次 pass：execute 之后必定 cleanup，并返回本次调度结果。

    cleanup 是 pass 的收尾阶段，必须在 execute 抛异常时也执行，避免临时动作组件
    残留在半完成的世界里。失败路径的 cleanup 异常只记录，不覆盖原始 processor
    异常。observer 由调用方显式传入；不传观测器时显式传 ``None``，pipeline 不会
    从任何全局上下文偷偷取默认值。

    ``StopPipeline`` 是显式的提前结束信号，不是错误：它在这里被消费，返回
    ``PassResult(aborted_by=...)``，不会抛给调用方。真正的失败仍然上抛，
    由上层（job / 会话）决定重试与状态处理。
    """
    try:
        await pipeline.execute(observer)
    except StopPipeline:
        pipeline.cleanup()
        return pipeline.last_pass
    except BaseException:
        try:
            pipeline.cleanup()
        except Exception:
            logger.exception("pipeline cleanup failed after execute error")
        raise

    pipeline.cleanup()
    return pipeline.last_pass


###############################################################################
def close_pipeline(
    pipeline: ProcessorPipeline,
    observer: Optional[ProcessorObserver] = None,
) -> None:
    """关闭 pipeline：tear_down 并清空反应式处理器已收集的实体。

    ``clear_reactive_processors`` 放在 ``finally`` 里：即使某一步 tear_down
    失败，已收集的实体也必须被释放。``tear_down`` 的失败策略与 observer
    由 pipeline 自身按 processor 声明处理。
    """
    try:
        pipeline.tear_down(observer)
    finally:
        pipeline.clear_reactive_processors()
