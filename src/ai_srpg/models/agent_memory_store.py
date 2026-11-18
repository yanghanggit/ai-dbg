"""Agent LLM 记忆容器。"""

from typing import Dict, Optional, final

from .agent_memory import AgentMemory


###############################################################################################################################################
@final
class AgentMemoryStore:
    """按实体名索引的 agent 记忆；只做容器与生命周期，不含消息策略。"""

    def __init__(self) -> None:
        self._memories: Dict[str, AgentMemory] = {}

    ###########################################################################
    def get_or_create(self, name: str) -> AgentMemory:
        """取得实体记忆；不存在时创建空记忆。"""
        return self._memories.setdefault(name, AgentMemory(name=name, messages=[]))

    ###########################################################################
    def get(self, name: str) -> Optional[AgentMemory]:
        """按实体名取记忆；不存在时返回 ``None``。"""
        return self._memories.get(name)

    ###########################################################################
    def remove(self, name: str) -> None:
        """移除实体记忆；不存在时静默忽略。"""
        self._memories.pop(name, None)

    ###########################################################################
    def all(self) -> Dict[str, AgentMemory]:
        """返回内部字典（只读用途；不要用它做结构性修改）。"""
        return self._memories

    ###########################################################################
    def __contains__(self, name: object) -> bool:
        return name in self._memories

    def __len__(self) -> int:
        return len(self._memories)


###############################################################################
__all__ = ["AgentMemoryStore"]
