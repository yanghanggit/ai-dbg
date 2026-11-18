"""一次游戏运行的组合快照：ECS 与 agent 记忆两个平级子系统。"""

from typing import Final, final

from pydantic import BaseModel

from .agent_memory_snapshot import AgentMemorySnapshot
from .context_snapshot import ContextSnapshot

#: 组合快照格式版本；子结构各自还有版本号。
GAME_SNAPSHOT_FORMAT_VERSION: Final[int] = 1


###############################################################################################################################################
@final
class GameSnapshot(BaseModel):
    """ECS 核心状态与 agent 记忆的成对快照。"""

    format_version: int = GAME_SNAPSHOT_FORMAT_VERSION
    ecs: ContextSnapshot
    memory: AgentMemorySnapshot

    ###########################################################################
    @property
    def game(self) -> str:
        """快照所属游戏名（取自 ECS 快照）。"""
        return self.ecs.game


###############################################################################
__all__ = ["GameSnapshot", "GAME_SNAPSHOT_FORMAT_VERSION"]
