"""消费 ``RefreshEnvironmentAction``：用 LLM 重写舞台的当前环境叙述。

只能读到舞台自身的历史：事件广播天生是「谁在场、谁做了什么」，读它等于把角色引进环境。
"""

from typing import Dict, List, final, override

from ...entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ...models import EnvironmentComponent, RefreshEnvironmentAction, StageComponent
from ...utils import prompt_builder
from ..context import SRPGGame
from .description_refresh_mixin import DescriptionRefreshMixin


@prompt_builder
def environment_prompt() -> str:
    """环境快照的任务说明。"""
    return """\
任务：写出该舞台此刻的环境快照。

只写舞台自身：空间、光、声、气温、气味，以及固定在其中的东西。
角色及其造成的变化都不写：谁在场、在做什么、带来了什么、留下了什么。
不依据在场者推断任何东西：不写只因他们在此才会出现的东西。
不写心理、推断、预告。不出现角色名。
输出：一段话，120 字以内，只输出正文，不加任何标记。"""


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
        """只处理仍挂着动作的舞台：写回组件会再派发一次 added，靠动作是否还在筛掉回声。"""
        return entity.has(StageComponent, RefreshEnvironmentAction)

    ##########################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        texts = await self.complete_descriptions(
            entities,
            label="environment",
            instruction=environment_prompt(),
            include_events=False,
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
__all__ = ["EnvironmentRefreshSystem", "environment_prompt"]
