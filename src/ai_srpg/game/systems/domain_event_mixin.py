"""发布领域事件：把「发生了一件事」交给游戏的事件出口。

投递是「谁听见」，发布是「记下发生过什么」，两件事分开做，所以这个 mixin 只管发布；
把消息说给谁听由 ``StageBroadcastMixin`` 负责，它继承本 mixin。于是一个会说话的
system 两样都够用，且都经 mixin 动手——「谁在哪个 system 里做了什么」在调用点可读。
"""

from ...models import AnyAgentEvent
from ..events.publish import publish_event
from .system_mixin import SystemMixin


class DomainEventMixin(SystemMixin):
    """把这一轮发生的领域事件交出去。"""

    ##########################################################################################
    def publish(self, agent_event: AnyAgentEvent) -> None:
        """发布一条事件；世界已经改好之后调用，一次变化只发一条。"""
        publish_event(self._game, agent_event)


###############################################################################
__all__ = ["DomainEventMixin"]
