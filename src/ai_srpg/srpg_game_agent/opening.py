"""副本开场房间动作骨架。

当前实现已清空：开场初始化只记录调用参数。
"""

from pathlib import Path

from .core import log_call


###############################################################################
async def init_opening_game(snapshot: Path) -> None:
    """开场房间初始化（骨架）。"""
    log_call("init_opening_game", snapshot=snapshot)
