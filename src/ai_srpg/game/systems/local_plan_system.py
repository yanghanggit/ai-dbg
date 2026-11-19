"""据点内的计划：这一刻的区域、在场者与相邻区域。

据点内部是场所：有环境、有在场者、有可以走过去的相邻区域，也可以出城回战场上。
"""

from typing import (
    Awaitable,
    Callable,
    Dict,
    Final,
    List,
    Tuple,
    Type,
    Union,
    final,
    override,
)

from ...entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ...entitas.components import Component
from ...llm import ToolDefinition, ToolFunction
from ...models import (
    ActorComponent,
    ActorExitStageAction,
    ActorMoveWithinStageAction,
    ActorPlanAction,
    ActorSpeakAction,
    ActorWaitAction,
    AppearanceComponent,
    EnvironmentComponent,
)
from ...utils import prompt_builder
from ..context import SRPGGame
from ..entities.queries import (
    get_actors_in_stage,
    get_adjacent_stages,
    is_on_map,
    resolve_stage_entity,
)
from .actor_plan_mixin import ActorPlanMixin

_NO_ENVIRONMENT: Final[str] = "（暂无环境描述）"

############################################################################################################
# 据点内能发起的行为
_SPEAK_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="speak",
        description="对同一区域里的人说一句话或一段话。",
        parameters={
            "type": "object",
            "properties": {"content": {"type": "string", "description": "要说的话"}},
            "required": ["content"],
        },
    )
)

_MOVE_WITHIN_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="move_within",
        description="在据点内部走到一个相邻的区域（子区域或父区域）。",
        parameters={
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "目标区域的名字"}
            },
            "required": ["destination"],
        },
    )
)

_EXIT_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="exit",
        description="离开这个据点，回到战场上它所在的那一格。",
        parameters={"type": "object", "properties": {}},
    )
)

_WAIT_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="wait",
        description="这一轮什么都不做，留在原地。",
        parameters={"type": "object", "properties": {}},
    )
)

_LOCAL_TOOLS: Final[List[ToolDefinition]] = [
    _SPEAK_TOOL,
    _MOVE_WITHIN_TOOL,
    _EXIT_TOOL,
    _WAIT_TOOL,
]

_LOCAL_ACTIONS: Final[Tuple[Type[Component], ...]] = (
    ActorSpeakAction,
    ActorMoveWithinStageAction,
    ActorExitStageAction,
    ActorWaitAction,
)


############################################################################################################
@prompt_builder
def local_plan_prompt(
    *, stage_name: str, environment: str, actors: List[str], destinations: List[str]
) -> str:
    """据点内计划的任务说明：这一刻的区域、环境、在场者与相邻区域。"""
    lines = [f"当前区域：{stage_name}", f"环境：{environment}", "", "在场角色："]
    lines.extend(f"- {actor}" for actor in actors)
    lines.extend(["", "可去之处："])
    lines.extend(f"- {item}" for item in destinations)
    if not destinations:
        lines.append("- 无")
    lines.extend(
        [
            "",
            "用工具表达你这一轮的行动：说话、在据点内移动、出城，或者原地不动。一次只做一件事。",
        ]
    )
    return "\n".join(lines)


############################################################################################################
@final
class LocalPlanSystem(ReactiveProcessor, ActorPlanMixin):
    """消费 ``ActorPlanAction``：给据点里的角色跑一轮计划。"""

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
        """只处理仍在据点里、且挂着计划动作的角色。"""
        return entity.has(ActorComponent, ActorPlanAction) and not is_on_map(
            self._game, entity
        )

    ##########################################################################################
    @override
    def allowed_actions(self) -> Tuple[Type[Component], ...]:
        return _LOCAL_ACTIONS

    ##########################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        for entity in sorted(entities, key=lambda item: item.index):
            await self.run_plan(
                entity,
                input_message=self._input_message(entity),
                tools=_LOCAL_TOOLS,
                handlers=self._handlers(entity),
            )

    ##########################################################################################
    def _input_message(self, entity: Entity) -> str:
        stage_entity = resolve_stage_entity(self._game, entity)
        assert stage_entity is not None, f"{entity.name} 无所在舞台"
        return local_plan_prompt(
            stage_name=stage_entity.name,
            environment=_environment_of(stage_entity),
            actors=[
                _describe_actor(actor)
                for actor in sorted(
                    get_actors_in_stage(self._game, stage_entity),
                    key=lambda item: item.index,
                )
            ],
            destinations=[
                stage.name for stage in get_adjacent_stages(self._game, entity)
            ],
        )

    ##########################################################################################
    def _handlers(
        self, entity: Entity
    ) -> Dict[str, Callable[..., Union[str, Awaitable[str]]]]:
        return {
            "speak": lambda content: self.mount_action(
                entity, ActorSpeakAction, content
            ),
            "move_within": lambda destination: self.mount_action(
                entity, ActorMoveWithinStageAction, destination
            ),
            "exit": lambda: self.mount_action(entity, ActorExitStageAction),
            "wait": lambda: self.mount_action(entity, ActorWaitAction),
        }


############################################################################################################
def _environment_of(stage_entity: Entity) -> str:
    if not stage_entity.has(EnvironmentComponent):
        return _NO_ENVIRONMENT
    return stage_entity.get(EnvironmentComponent).narrative


############################################################################################################
def _describe_actor(actor: Entity) -> str:
    """一行一个角色：名字加此刻的样子。"""
    if not actor.has(AppearanceComponent):
        return actor.name
    return f"{actor.name}：{actor.get(AppearanceComponent).appearance}"


###############################################################################
__all__ = ["LocalPlanSystem", "local_plan_prompt"]
