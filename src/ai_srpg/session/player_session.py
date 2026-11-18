"""用户级会话历史（聚合根）。

会话不随某一局 ``SRPGGame`` 重置：游戏是客户端当前看到的世界，会话是脱离游戏的
上帝视角。``actor`` / ``game`` 只表示当前上下文，每条 ``SessionMessage`` 自己记录
产生时的 game / actor / job。

放在 ``session`` 包而不是 ``models``：它是**有行为与不变量的运行期聚合**（追加时
分配全局序号、按序号增量读取），不是可自由构造的传输/快照数据；DTO 仍在
``models.session_message``。
"""

from typing import List, Optional, final

from pydantic import BaseModel

from ..models import AnyAgentEvent, SessionMessage


###############################################################################
@final
class PlayerSession(BaseModel):
    """用户级、append-only 的会话历史。"""

    # 玩家的唯一标识符(通常是用户名)
    name: str

    # 玩家当前控制的游戏角色名称（当前上下文，不是历史身份）
    actor: Optional[str] = None

    # 当前游戏名字（当前上下文，不是历史身份）
    game: Optional[str] = None

    # 会话的完整消息/事件历史列表，按 sequence_id 递增
    session_messages: List[SessionMessage] = []

    # 全局事件序号，跨游戏持续递增
    event_sequence: int = 0

    ###############################################################################
    def set_context(self, *, actor: Optional[str], game: Optional[str]) -> None:
        """更新当前游戏上下文；不会清理历史消息与序号。"""
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
        """追加一条代理事件，并返回已经分配序号的 ``SessionMessage``。"""
        agent_event_message = SessionMessage(
            agent_event=agent_event,
            job_id=job_id,
            game_name=game_name if game_name is not None else self.game,
            actor=actor if actor is not None else self.actor,
        )
        return self._add_session_message(agent_event_message)

    ###############################################################################
    def _add_session_message(self, message: SessionMessage) -> SessionMessage:
        """内部方法：添加会话消息并分配序列号。"""
        self.event_sequence += 1
        message.sequence_id = self.event_sequence
        self.session_messages.append(message)
        return message

    ###############################################################################
    def get_messages_since(self, last_id: int) -> List[SessionMessage]:
        """获取指定序列号之后的所有消息（增量获取）。"""
        return [e for e in self.session_messages if e.sequence_id > last_id]
