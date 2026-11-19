"""找出当前描述仍等于底稿的实体，挂上刷新动作。

自动路径的守卫只在这里：已改写过的描述不再挂，想强制重写就直接挂同一个动作。
动作每轮由 ``ActionCleanupSystem`` 清掉，因此每轮重新判定。
"""

from typing import List, Type, final, override

from ...entitas import Entity, ExecuteProcessor, Matcher
from ...entitas.components import Component
from ...models import (
    ActorComponent,
    AppearanceComponent,
    EnvironmentComponent,
    RefreshAppearanceAction,
    RefreshEnvironmentAction,
    StageComponent,
)
from .system_mixin import SystemMixin


@final
class StaleDescriptionSystem(SystemMixin, ExecuteProcessor):
    """给尚未定制过描述的角色与舞台挂刷新动作。"""

    ##########################################################################################
    @override
    async def execute(self) -> None:
        for entity in self._entities_with(ActorComponent, AppearanceComponent):
            appearance = entity.get(AppearanceComponent)
            if appearance.appearance == appearance.base_body:
                self._request(entity, RefreshAppearanceAction)

        for entity in self._entities_with(StageComponent, EnvironmentComponent):
            environment = entity.get(EnvironmentComponent)
            if environment.narrative == environment.base_environment:
                self._request(entity, RefreshEnvironmentAction)

    ##########################################################################################
    def _entities_with(self, *components: Type[Component]) -> List[Entity]:
        """按组件组合取实体，按创建顺序排列。"""
        entities = self._game.get_group(Matcher(all_of=components)).entities
        return sorted(entities, key=lambda entity: entity.index)

    ##########################################################################################
    def _request(self, entity: Entity, action: Type[Component]) -> None:
        """挂动作；已挂过就跳过。"""
        if not entity.has(action):
            entity.replace(action)
