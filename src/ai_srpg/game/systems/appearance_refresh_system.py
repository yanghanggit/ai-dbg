"""消费 ``RefreshAppearanceAction``：用 LLM 重写角色的当前外观。

外观是「旁人此刻看到的样子」，不是设定稿：设定只在被当下状态改变时才该出现。
动作由 ``StaleDescriptionSystem`` 按状态守卫自动挂上，也可以由别处直接挂上来强制重写。
生成失败时保留原样，``base_body`` 永远不动。
"""

from typing import Dict, List, final, override

from ...entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ...models import ActorComponent, AppearanceComponent, RefreshAppearanceAction
from ..context import SRPGGame
from .description_refresh_mixin import DescriptionRefreshMixin

#: 交给模型的唯一任务说明；历史一律是该角色自己的 agent 记忆
APPEARANCE_INSTRUCTION = """\
依据你记忆里的设定与最近发生的事，写出「此刻」你的样子。

- 用旁观视角、第三人称：只写可见的东西——衣着、装备、伤势、污渍、姿态与神情。
- 写这一刻的状态，不写履历；设定里写过的容貌，只在被当下状态改变时才提起。
- 不写心理活动，不做推断，不叙述经历，也不要解释你为什么这样写。
- 只输出描述本身：一段话，120 字以内；不要加括号、引号、标题或任何标记。"""


@final
class AppearanceRefreshSystem(ReactiveProcessor, DescriptionRefreshMixin):
    """把待刷新的角色外观交给 LLM，写回 ``AppearanceComponent.appearance``。"""

    ##########################################################################################
    def __init__(self, game: SRPGGame) -> None:
        ReactiveProcessor.__init__(self, game)
        DescriptionRefreshMixin.__init__(self, game)

    ##########################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {
            Matcher(
                all_of=[RefreshAppearanceAction, AppearanceComponent]
            ): GroupEvent.ADDED
        }

    ##########################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        """只处理仍挂着动作的角色。

        写回组件时 group 会同时派发「added」，实体因此重新进入收集器；这里连同动作
        一起判断，把那次回声筛掉——否则每轮都会重复生成。动作已被清理也走这条。
        """
        return entity.has(ActorComponent, RefreshAppearanceAction)

    ##########################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        texts = await self.complete_descriptions(
            entities, label="appearance", instruction=APPEARANCE_INSTRUCTION
        )
        for entity in entities:
            text = texts.get(entity.name)
            if text is None:
                continue
            appearance = entity.get(AppearanceComponent)
            entity.replace(AppearanceComponent, appearance.base_body, text)
            self.record_description_update(
                entity,
                description=text,
                current_label="外观",
                base_label="基础体型",
                base=appearance.base_body,
            )


###############################################################################
__all__ = ["APPEARANCE_INSTRUCTION", "AppearanceRefreshSystem"]
