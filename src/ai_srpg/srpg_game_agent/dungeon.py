"""副本生命周期动作骨架。

当前实现已清空：进入、推进与退出副本只记录调用参数。
"""

from pathlib import Path

from .core import log_call


###############################################################################
async def enter_dungeon_game(snapshot: Path, dungeon: str) -> None:
    """从大厅进入指定副本（骨架）。"""
    log_call("enter_dungeon_game", snapshot=snapshot, dungeon=dungeon)


###############################################################################
async def next_dungeon_game(snapshot: Path) -> None:
    """推进到下一个房间（骨架）。"""
    log_call("next_dungeon_game", snapshot=snapshot)


###############################################################################
async def exit_dungeon_game(snapshot: Path) -> None:
    """退出副本回到大厅（骨架）。"""
    log_call("exit_dungeon_game", snapshot=snapshot)
