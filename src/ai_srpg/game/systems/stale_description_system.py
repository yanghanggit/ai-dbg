"""找出「当前描述还停在底稿」的实体，标记为待刷新。

这是自动路径的状态守卫，也是唯一的判定点：只有外观还是 ``base_body``、环境还是
``base_environment`` 时才挂动作。已经被改写过的描述不会每轮重写一遍——想强制重写，
在别处直接挂同一个动作即可（主动路径）。

动作组件在 pipeline 收尾由 ``ActionCleanupSystem`` 清除，所以每轮重新判定。
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
    """为描述尚未定制过的角色与舞台挂上刷新动作。"""

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
        """按组件组合取实体，按创建顺序排列（与快照重放一致）。"""
        entities = self._game.get_group(Matcher(all_of=components)).entities
        return sorted(entities, key=lambda entity: entity.index)

    ##########################################################################################
    def _request(self, entity: Entity, action: Type[Component]) -> None:
        """挂动作；已挂过就不再挂（同轮重复调用幂等）。"""
        if not entity.has(action):
            entity.replace(action)
