"""游戏内工具（供 agent 调用，不属于 pipeline processor）。"""

from .knowledge_query import search_knowledge_base

__all__ = ["search_knowledge_base"]
