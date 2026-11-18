"""游戏领域事件出口。

系统只负责把发生的领域事件发布到 sink；谁订阅（玩家会话、job 日志、
未来的 replay/审计）由应用层决定。``SRPGGame`` 因此不需要知道
``PlayerSession`` 的存在。
"""

from typing import List, Protocol

from ..models import AnyAgentEvent


###############################################################################
class DomainEventSink(Protocol):
    """接收游戏领域事件的最小接口。"""

    def publish(self, agent_event: AnyAgentEvent) -> None:
        """发布一个领域事件。"""


###############################################################################
class NullEventSink:
    """默认 sink：没有订阅者时丢弃事件。"""

    def publish(self, agent_event: AnyAgentEvent) -> None:
        return None


###############################################################################
class RecordingEventSink:
    """仅用于测试/调试的内存 sink。"""

    def __init__(self) -> None:
        self.events: List[AnyAgentEvent] = []

    def publish(self, agent_event: AnyAgentEvent) -> None:
        self.events.append(agent_event)
