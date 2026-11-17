"""Pipeline 收尾清理动作组件，避免动作跨 pass 残留。"""

from typing import Final, FrozenSet, Mapping, Type, final, override

from ..entitas import CleanupProcessor, ExecuteProcessor, Matcher
from ..entitas.components import Component
from ..game.context import DBGGame
from ..models import (
    ACTION_COMPONENT_TYPES,
)


@final
class ActionCleanupSystem(ExecuteProcessor, CleanupProcessor):
    """在 execute 尾部与 cleanup 兜底两个阶段清理动作组件。

    execute 是正常运行时的清理点；cleanup 是 execute 提前失败后的兜底。
    两个入口调用同一个同步清理函数，重复执行是幂等的。
    """

    ############################################################################################################
    def __init__(
        self,
        game: DBGGame,
        action_component_types: Mapping[str, Type[Component]] = ACTION_COMPONENT_TYPES,
    ) -> None:
        self._game: Final[DBGGame] = game
        self._registered_actions: Final[FrozenSet[Type[Component]]] = frozenset(
            action_component_types.values()
        )

    ############################################################################################################
    @override
    async def execute(self) -> None:
        self._clear_actions()

    ############################################################################################################
    @override
    def cleanup(self) -> None:
        self._clear_actions()

    ############################################################################################################
    def _clear_actions(self) -> None:

        # 清除行动！
        action_entities = self._game.ecs.get_group(
            Matcher(any_of=self._registered_actions)
        ).entities.copy()

        for entity in action_entities:
            for action_class in self._registered_actions:
                if entity.has(action_class):
                    entity.remove(action_class)

        # 确认一下！
        cleared_entities = self._game.ecs.get_group(
            Matcher(any_of=self._registered_actions)
        ).entities
        assert len(cleared_entities) == 0, f"entities with actions: {cleared_entities}"
