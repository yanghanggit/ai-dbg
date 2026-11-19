"""Pipeline 首端：每轮开跑前检查全局不变量，第一项是「角色都在舞台上」。"""

from typing import final, override

from loguru import logger

from ...entitas import ExecuteProcessor, Matcher
from ...models import ActorComponent
from ..entities import get_stage_entity
from .system_mixin import SystemMixin


@final
class PrologueSystem(SystemMixin, ExecuteProcessor):
    """Pipeline 首端占位系统：只做不变量检查，其余前置操作留待将来扩展。"""

    ############################################################################################################
    @override
    async def execute(self) -> None:
        logger.debug("🚀 Pipeline 起始系统执行 - PrologueSystem")
        self._assert_actors_on_stage()

    ############################################################################################################
    def _assert_actors_on_stage(self) -> None:
        """角色必须站在一个存在的舞台上——不存在「不在场」的角色状态。

        下游一律按 ``ActorComponent.current_stage`` 反查舞台，空值或悬空名字会让
        分组与广播静默漏人，所以在每轮入口炸出来。
        """
        actors = self._game.get_group(Matcher(all_of=[ActorComponent])).entities
        for actor in actors:
            stage_name = actor.get(ActorComponent).current_stage
            assert (
                stage_name.strip() != ""
            ), f"角色 {actor.name} 没有所在舞台(current_stage)"
            assert (
                get_stage_entity(self._game, stage_name) is not None
            ), f"角色 {actor.name} 的所在舞台不存在: {stage_name}"
