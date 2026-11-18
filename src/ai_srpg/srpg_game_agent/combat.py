"""战斗动作骨架。

当前实现已清空：每个动作只记录调用参数，待 SRPG 战斗规则落地后补充。
"""

from pathlib import Path
from typing import Sequence

from .core import log_call


###############################################################################
async def init_combat_game(snapshot: Path) -> None:
    """战斗房间初始化（骨架）。"""
    log_call("init_combat_game", snapshot=snapshot)


###############################################################################
async def pass_turn_game(snapshot: Path, actor: str) -> None:
    """交出行动权（骨架）。"""
    log_call("pass_turn_game", snapshot=snapshot, actor=actor)


###############################################################################
async def use_consumable_game(
    snapshot: Path, item: str, targets: Sequence[str]
) -> None:
    """使用消耗品（骨架）。"""
    log_call("use_consumable_game", snapshot=snapshot, item=item, targets=list(targets))


###############################################################################
async def retreat_game(snapshot: Path) -> None:
    """主动撤退（骨架）。"""
    log_call("retreat_game", snapshot=snapshot)
