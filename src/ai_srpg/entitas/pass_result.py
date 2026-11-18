"""一次 pass 的结果。

pipeline 只区分「正常跑完」与「显式提前结束」；普通异常不进入结果对象，
直接上抛给上层（由快照回滚兜底）。
"""

from dataclasses import dataclass
from typing import Optional, Tuple


###############################################################################
@dataclass(frozen=True)
class PassResult:
    """一次 ``execute()`` 的调度结果。

    - ``ran``：正常返回的 processor（按执行顺序）。
    - ``skipped``：因显式提前结束而未被执行的 processor。
    - ``aborted_by``：显式要求提前结束的 processor；正常跑完为 ``None``。
    """

    ran: Tuple[str, ...] = ()
    skipped: Tuple[str, ...] = ()
    aborted_by: Optional[str] = None

    ###########################################################################
    @property
    def completed(self) -> bool:
        """所有 processor 都执行到了（没有被提前结束截断）。"""
        return self.aborted_by is None and not self.skipped


__all__ = ["PassResult"]
