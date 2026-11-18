"""一次 pass 的结果。

pipeline 只定义「跑没跑完、谁失败了、谁被跳过」，不解释失败的业务含义：
严重性、重试、状态复位属于上层（job / 会话 / 玩法）的职责。
"""

from dataclasses import dataclass
from typing import Optional, Tuple


###############################################################################
@dataclass(frozen=True)
class ProcessorFailure:
    """单个 processor 的失败记录。"""

    system: str
    error: BaseException
    duration_ms: float


###############################################################################
@dataclass(frozen=True)
class PassResult:
    """一次 ``execute()`` 的调度结果。

    - ``ran``：正常返回的 processor（按执行顺序）。
    - ``failures``：抛异常的 processor；是否中断 pass 由 ``ErrorPolicy`` 决定。
    - ``skipped``：因失败传播或提前结束而未被执行的 processor。
    - ``aborted_by``：显式要求提前结束的 processor；正常跑完为 ``None``。
    """

    ran: Tuple[str, ...] = ()
    failures: Tuple[ProcessorFailure, ...] = ()
    skipped: Tuple[str, ...] = ()
    aborted_by: Optional[str] = None

    ###########################################################################
    @property
    def completed(self) -> bool:
        """所有 processor 都正常执行（允许存在被 ``CONTINUE`` 记录的失败）。"""
        return self.aborted_by is None and not self.skipped

    @property
    def interrupted(self) -> bool:
        """因失败策略传播而中断（区别于显式提前结束）。"""
        return self.aborted_by is None and bool(self.skipped)


__all__ = ["PassResult", "ProcessorFailure"]
