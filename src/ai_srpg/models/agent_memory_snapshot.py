"""Agent 记忆快照信封。

与 ``ContextSnapshot`` 平级：ECS 只关心实体/组件，这里只关心按实体名索引的
LLM 记忆。两者由上层（job / 会话）一起提交或一起回滚。
"""

from typing import Dict, Final, final

from pydantic import BaseModel

from .agent_memory import AgentMemory

#: 记忆快照格式版本；``AgentMemory`` 结构变化时递增并集中迁移。
MEMORY_SNAPSHOT_FORMAT_VERSION: Final[int] = 1


###############################################################################################################################################
@final
class AgentMemorySnapshot(BaseModel):
    """一次 agent 记忆状态的不可变快照（实体名 → 记忆）。"""

    format_version: int = MEMORY_SNAPSHOT_FORMAT_VERSION
    memories: Dict[str, AgentMemory]


###############################################################################
__all__ = ["AgentMemorySnapshot", "MEMORY_SNAPSHOT_FORMAT_VERSION"]
