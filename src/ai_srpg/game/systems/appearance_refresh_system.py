"""消费 ``RefreshAppearanceAction``：用 LLM 重写角色的当前外观。

外观是定格快照而非叙事片段；``base_body`` 永不改写。
"""

from typing import Dict, List, final, override

from ...entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ...models import ActorComponent, AppearanceComponent, RefreshAppearanceAction
from ...utils import prompt_builder
from ..context import SRPGGame
from .description_refresh_mixin import DescriptionRefreshMixin


@prompt_builder
def appearance_prompt() -> str:
    """外观快照的任务说明。"""
    return """\
任务：写出该角色此刻的外观快照。

只写定格照片里能看见的部分。
不写动作、姿态、场景、在场者、心理、履历与解释。
不出现名字，不用「你」「他」作主语。
输出：一段话，120 字以内，只输出正文，不加任何标记。"""


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
        """只处理仍挂着动作的角色：写回组件会再派发一次 added，靠动作是否还在筛掉回声。"""
        return entity.has(ActorComponent, RefreshAppearanceAction)

    ##########################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        texts = await self.complete_descriptions(
            entities, label="appearance", instruction=appearance_prompt()
        )
        for entity in entities:
            entity.remove(RefreshAppearanceAction)  # 处理即消费
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
__all__ = ["AppearanceRefreshSystem", "appearance_prompt"]
