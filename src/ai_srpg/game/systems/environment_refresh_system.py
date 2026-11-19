"""消费 ``RefreshEnvironmentAction``：用 LLM 重写舞台的当前环境叙述。

环境快照只描述舞台自身的物理状态。谁在场、谁做了什么、留下了什么痕迹，都属于角色
自己的状态，不属于环境——所以任务说明里明确禁止写人，历史里的在场消息只用来判断
光线、声音与温度的变化。
"""

from typing import Dict, List, final, override

from ...entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ...models import EnvironmentComponent, RefreshEnvironmentAction, StageComponent
from ..context import SRPGGame
from .description_refresh_mixin import DescriptionRefreshMixin

#: 交给模型的唯一任务说明；历史一律是该舞台自己的 agent 记忆
ENVIRONMENT_INSTRUCTION = """\
依据你记忆里的舞台设定与最近发生的事，写出「此刻」这个舞台的环境快照。

- 只写舞台自身的物理状态：光线、温度、气味、声音、地形、地面上原有的东西。
- 不写人，也不写人留下的东西：谁在场、谁做了什么、行李、火堆、脚印、血迹都不算环境。
- 不写心理活动，不做推断，不预告下一步会发生什么。
- 只输出描述本身：一段话，120 字以内；不要加括号、引号、标题或任何标记。"""


@final
class EnvironmentRefreshSystem(ReactiveProcessor, DescriptionRefreshMixin):
    """把待刷新的舞台环境交给 LLM，写回 ``EnvironmentComponent.narrative``。"""

    ##########################################################################################
    def __init__(self, game: SRPGGame) -> None:
        ReactiveProcessor.__init__(self, game)
        DescriptionRefreshMixin.__init__(self, game)

    ##########################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {
            Matcher(
                all_of=[RefreshEnvironmentAction, EnvironmentComponent]
            ): GroupEvent.ADDED
        }

    ##########################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        """只处理仍挂着动作的舞台。

        写回组件时 group 会同时派发「added」，实体因此重新进入收集器；这里连同动作
        一起判断，把那次回声筛掉——否则每轮都会重复生成。动作已被清理也走这条。
        """
        return entity.has(StageComponent, RefreshEnvironmentAction)

    ##########################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        texts = await self.complete_descriptions(
            entities, label="environment", instruction=ENVIRONMENT_INSTRUCTION
        )
        for entity in entities:
            text = texts.get(entity.name)
            if text is None:
                continue
            environment = entity.get(EnvironmentComponent)
            entity.replace(EnvironmentComponent, environment.base_environment, text)
            self.record_description_update(
                entity,
                description=text,
                current_label="环境",
                base_label="环境底稿",
                base=environment.base_environment,
            )


###############################################################################
__all__ = ["ENVIRONMENT_INSTRUCTION", "EnvironmentRefreshSystem"]
