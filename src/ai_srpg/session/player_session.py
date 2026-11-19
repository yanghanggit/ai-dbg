"""用户级会话历史的游标与上下文指针。

历史消息本身是 append-only 的持久化数据（见 ``pgsql.session_messages``），不在
内存里累积；这个聚合只负责两件事：分配用户级递增序号、承载「当前游戏/角色」指针。

因此它可以在任何进程里从存储恢复：按最大序号构造，追加时递增，读历史走存储层。
"""

from typing import Optional, final

from pydantic import BaseModel

from ..models import AnyAgentEvent, SessionMessage


###############################################################################
@final
class PlayerSession(BaseModel):
    """用户级会话：脱离单局游戏的「上帝视角」。"""

    # 账号标识（与房间、会话历史、快照用同一个词）
    user_name: str

    # 玩家当前控制的游戏角色名称（当前上下文，不是历史身份）
    actor: Optional[str] = None

    # 当前游戏名字（当前上下文，不是历史身份）
    game: Optional[str] = None

    # 已分配的最大事件序号，跨游戏持续递增；从存储恢复
    event_sequence: int = 0

    ###############################################################################
    def set_context(self, *, actor: Optional[str], game: Optional[str]) -> None:
        """更新当前游戏上下文；不影响历史与序号。"""
        self.actor = actor
        self.game = game

    ###############################################################################
    def add_agent_event(
        self,
        agent_event: AnyAgentEvent,
        *,
        job_id: Optional[int] = None,
        game_name: Optional[str] = None,
        actor: Optional[str] = None,
    ) -> SessionMessage:
        """分配序号并构造一条 ``SessionMessage``；落盘由调用方（sink）负责。"""
        self.event_sequence += 1
        return SessionMessage(
            agent_event=agent_event,
            sequence_id=self.event_sequence,
            job_id=job_id,
            game_name=game_name if game_name is not None else self.game,
            actor=actor if actor is not None else self.actor,
        )
