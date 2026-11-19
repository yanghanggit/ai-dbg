"""战役地图上的计划：这一刻站在哪一格、视野里的相邻格上有什么。

地图不是场所：没有在场者、也没有环境，只有坐标、据点，以及站在格上的别人。
"""

from typing import Awaitable, Callable, Dict, Final, List, Tuple, Type, final, override

from ...entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ...entitas.components import Component
from ...llm import ToolDefinition, ToolFunction
from ...models import (
    ActorComponent,
    ActorEnterStageAction,
    ActorPlanAction,
    ActorTravelAction,
    ActorWaitAction,
)
from ...utils import prompt_builder
from ..context import SRPGGame
from ..entities.queries import (
    Cell,
    get_cell,
    get_map_cells,
    get_stage_at_cell,
    is_on_map,
)
from .actor_plan_mixin import ActorPlanMixin

############################################################################################################
# 地图上能发起的行为
_TRAVEL_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="travel",
        description="在战场上移动到相邻的一格。",
        parameters={
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "目标格子的横坐标"},
                "y": {"type": "integer", "description": "目标格子的纵坐标"},
            },
            "required": ["x", "y"],
        },
    )
)

_ENTER_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="enter",
        description="走进脚边的那一个据点。只有站在据点所在的格子上才能进。",
        parameters={
            "type": "object",
            "properties": {
                "stage": {"type": "string", "description": "要进的据点名字"}
            },
            "required": ["stage"],
        },
    )
)

_WAIT_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="wait",
        description="这一轮什么都不做，留在原地。",
        parameters={"type": "object", "properties": {}},
    )
)

_GLOBAL_TOOLS: Final[List[ToolDefinition]] = [_TRAVEL_TOOL, _ENTER_TOOL, _WAIT_TOOL]

_GLOBAL_ACTIONS: Final[Tuple[Type[Component], ...]] = (
    ActorTravelAction,
    ActorEnterStageAction,
    ActorWaitAction,
)


############################################################################################################
@prompt_builder
def global_plan_prompt(*, location: str, cells: List[str]) -> str:
    """地图上计划的任务说明：这一刻的位置与视野内的相邻格。"""
    lines = [f"当前位置：{location}", "", "视野："]
    lines.extend(f"- {cell}" for cell in cells)
    lines.extend(
        [
            "",
            "用工具表达你这一轮的行动：在战场上移动到相邻一格、进城，或者原地不动。一次只做一件事。",
        ]
    )
    return "\n".join(lines)


############################################################################################################
@final
class GlobalPlanSystem(ReactiveProcessor, ActorPlanMixin):
    """消费 ``ActorPlanAction``：给站在地图上的角色跑一轮计划。"""

    ##########################################################################################
    def __init__(self, game: SRPGGame) -> None:
        ReactiveProcessor.__init__(self, game)
        ActorPlanMixin.__init__(self, game)

    ##########################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(all_of=[ActorPlanAction, ActorComponent]): GroupEvent.ADDED}

    ##########################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        """只处理站在地图上、且挂着计划动作的角色。"""
        return entity.has(ActorComponent, ActorPlanAction) and is_on_map(
            self._game, entity
        )

    ##########################################################################################
    @override
    def allowed_actions(self) -> Tuple[Type[Component], ...]:
        return _GLOBAL_ACTIONS

    ##########################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        for entity in sorted(entities, key=lambda item: item.index):
            await self.run_plan(
                entity,
                input_message=self._input_message(entity),
                tools=_GLOBAL_TOOLS,
                handlers=self._handlers(entity),
            )

    ##########################################################################################
    def _input_message(self, entity: Entity) -> str:
        map_entity, (x, y) = get_cell(self._game, entity)
        here = get_stage_at_cell(self._game, map_entity, (x, y))
        return global_plan_prompt(
            location=f"({x},{y}) {here.name if here is not None else '空地'}",
            cells=[
                _describe_cell(cell)
                for cell in get_map_cells(self._game, entity)
                if (cell.x, cell.y) != (x, y)
            ],
        )

    ##########################################################################################
    def _handlers(
        self, entity: Entity
    ) -> Dict[str, Callable[..., Awaitable[str] | str]]:
        return {
            "travel": lambda x, y: self.mount_action(entity, ActorTravelAction, x, y),
            "enter": lambda stage: self.mount_action(
                entity, ActorEnterStageAction, stage
            ),
            "wait": lambda: self.mount_action(entity, ActorWaitAction),
        }


############################################################################################################
def _describe_cell(cell: Cell) -> str:
    """一格一行：坐标、格上的据点（或空地），以及在格上的角色。"""
    where = cell.stage if cell.stage is not None else "空地"
    line = f"({cell.x},{cell.y}) {where}"
    if cell.actors:
        line = f"{line}，在场 {'、'.join(cell.actors)}"
    return line


###############################################################################
__all__ = ["GlobalPlanSystem", "global_plan_prompt"]
