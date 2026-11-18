"""游戏动作骨架：新局创建与场景名单。

当前实现已清空：动作只记录调用参数，不读写世界状态。
待数据层与 SRPG 规则落地后在此补充。
"""

from pathlib import Path
from typing import Dict, List

from loguru import logger


###############################################################################
def log_call(action: str, **params: object) -> None:
    """统一记录骨架调用的参数，便于确认 CLI 契约。"""
    logger.info(f"[skeleton] {action}: {params}")


###############################################################################
async def create_and_initialize_game(user: str, game: str, dungeon: str) -> None:
    """创建并初始化一局游戏（骨架）。"""
    log_call(
        "create_and_initialize_game",
        user=user,
        game=game,
        dungeon=dungeon,
    )


###############################################################################
async def stages_game(snapshot: Path) -> Dict[str, List[str]]:
    """返回各场景内角色名单（骨架：返回空映射）。"""
    log_call("stages_game", snapshot=snapshot)
    return {}
