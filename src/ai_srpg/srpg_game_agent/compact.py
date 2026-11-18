"""上下文压缩动作骨架。

当前实现已清空：手动压缩只记录调用参数。
"""

from typing import Optional

from .core import log_call


###############################################################################
async def compact_context_game(
    user: str, game: str, target: str, snapshot_id: Optional[int]
) -> None:
    """手动压缩指定实体的 LLM 记忆（骨架）。"""
    log_call(
        "compact_context_game",
        user=user,
        game=game,
        target=target,
        snapshot_id=snapshot_id,
    )
