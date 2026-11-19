"""角色名册：CLI 选人时看到的一行摘要。"""

from typing import Optional

from pydantic import BaseModel


############################################################################################################
class ActorSummary(BaseModel):
    """一个角色此刻的状态：在哪、谁在控制、看起来什么样。"""

    name: str
    stage: str
    player: Optional[str] = None
    appearance: str = ""


############################################################################################################
__all__ = ["ActorSummary"]
