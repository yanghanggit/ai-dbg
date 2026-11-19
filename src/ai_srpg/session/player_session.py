"""某席位在局级会话流上的游标与当前上下文指针。

序号由 ``Room`` 分配，这里只记录「我读到哪」。
"""

from typing import Optional, final

from pydantic import BaseModel

from ..models import AnyAgentEvent, SessionMessage


###############################################################################
@final
class PlayerSession(BaseModel):
    """某席位在局级会话流上的已读游标 + 当前上下文。"""

    # 账号标识（与房间、会话历史、快照用同一个词）
    user_name: str

    # 所在房间（一局游戏）；会话流按它划分
    room_id: str

    # 该席位当前控制的游戏角色名称（当前上下文，不是历史身份）
    actor: Optional[str] = None

    # 当前游戏名字（当前上下文，不是历史身份）
    game: Optional[str] = None

    # 在局级流上的已读序号；从流头构造，读到自己需要的进度
    event_sequence: int = 0

    ###############################################################################
    def set_context(self, *, actor: Optional[str], game: Optional[str]) -> None:
        """更新当前游戏上下文；不影响游标。"""
        self.actor = actor
        self.game = game

    ###############################################################################
    def build_message(
        self,
        agent_event: AnyAgentEvent,
        *,
        sequence_id: int,
        job_id: Optional[int] = None,
        game_name: Optional[str] = None,
        actor: Optional[str] = None,
        visible_to: Optional[str] = None,
    ) -> SessionMessage:
        """用给定的局级序号构造一条 ``SessionMessage``；落盘由调用方（sink）负责。"""
        return SessionMessage(
            agent_event=agent_event,
            sequence_id=sequence_id,
            job_id=job_id,
            game_name=game_name if game_name is not None else self.game,
            actor=actor if actor is not None else self.actor,
            user_name=visible_to,
        )
