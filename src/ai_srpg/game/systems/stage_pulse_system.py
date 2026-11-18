"""舞台心跳：每轮把舞台现状广播给舞台内的角色。

这是第一个会**发布领域事件**的 system：它不改世界结构，只把「此刻舞台里有哪些
角色」写成一条领域事件，经 ``broadcast_to_stage`` 同时进入两层下游——舞台与角色
的 agent 记忆，以及游戏的事件出口（由会话历史等订阅者消费）。

定位是「管线里第一个业务 system 的样板」：真实玩法替换或追加它时，发布链路与
job / 会话历史的关联方式保持不变。
"""

from typing import Final, final, override

from ...entitas import ExecuteProcessor
from ...models import NoneEvent
from ..context import SRPGGame
from ..entities import get_actors_by_stage
from ..events.publish import broadcast_to_stage


@final
class StagePulseSystem(ExecuteProcessor):
    """每轮为每个有角色的舞台广播一条现状事件。"""

    ############################################################################################################
    def __init__(self, game: SRPGGame) -> None:
        self._game: Final[SRPGGame] = game

    ############################################################################################################
    @override
    async def execute(self) -> None:
        # 空舞台不广播：没有角色时「谁在场」没有信息量，只会污染记忆与历史
        for stage_entity, actors in get_actors_by_stage(self._game).items():
            if not actors:
                continue

            names = "、".join(sorted(actor.name for actor in actors))
            broadcast_to_stage(
                self._game,
                stage_entity,
                NoneEvent(message=f"{stage_entity.name}：当前在场 {names}。"),
            )
