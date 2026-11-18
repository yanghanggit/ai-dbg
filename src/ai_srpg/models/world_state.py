from typing import Dict, final

from pydantic import BaseModel

from .agent_memory import AgentMemory


###############################################################################################################################################
# 世界状态（WorldState）：只放运行时状态。蓝图是构建期输入，不在此重复保存。
@final
class WorldState(BaseModel):
    entity_counter: int = 0
    agent_memories: Dict[str, AgentMemory] = {}


###############################################################################
