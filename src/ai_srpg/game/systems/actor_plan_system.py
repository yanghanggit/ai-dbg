"""角色计划：让角色在一轮里先想清要做什么，用自己的话与工具表达。

计划是「想」而不是「做」：工具只打日志，世界状态不变，留下的痕迹只是角色记忆里这次
loop 的对话。谁能被计划由调用方决定——挂上 ``ActorPlanAction`` 即可；计划失败就当这个
角色本轮轮空，不抛给 pipeline。
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

from loguru import logger

from ...deepseek import AgentLoopResult, agent_loop
from ...entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ...entitas.components import Component
from ...llm import ToolDefinition, ToolFunction
from ...models import (
    ActorComponent,
    ActorMoveAction,
    ActorPlanAction,
    ActorSpeakAction,
    ActorWaitAction,
    AppearanceComponent,
    EnvironmentComponent,
)
from ...utils import prompt_builder
from ..context import SRPGGame
from ..entities.queries import Exit, get_actors_in_stage, get_exits, get_stage_entity
from ..memory import get_agent_memory
from .system_mixin import SystemMixin

#: 最多往返几轮：够表达「说一句 + 走一步」，又不给模型自己绕圈的空间
_PLAN_ROUNDS: Final[int] = 3

_NO_ENVIRONMENT: Final[str] = "（暂无环境描述）"

############################################################################################################
# 计划这一步能发起的「行为」。两者都还是空转：只留痕，不改世界。
_SPEAK_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="speak",
        description="对在场的人说一句话或一段话。",
        parameters={
            "type": "object",
            "properties": {"content": {"type": "string", "description": "要说的话"}},
            "required": ["content"],
        },
    )
)

_MOVE_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="move",
        description="离开当前所在的位置，去别处。",
        parameters={
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "要去的地方，或往哪个方向走",
                }
            },
            "required": ["target"],
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

#: 三个工具都是终止工具：一次计划只落一个行动，说完、走完或不动就结束本轮
_PLAN_TOOLS: Final[List[ToolDefinition]] = [_SPEAK_TOOL, _MOVE_TOOL, _WAIT_TOOL]

#: 一轮只能落一个行动：模型在同一条回复里多调时，只有第一个生效
_BEHAVIOUR_ACTIONS: Final[Tuple[Type[Component], ...]] = (
    ActorSpeakAction,
    ActorMoveAction,
    ActorWaitAction,
)


############################################################################################################
@prompt_builder
def actor_plan_prompt(
    *, stage_name: str, environment: str, actors: List[str], exits: List[str]
) -> str:
    """计划任务说明：这一刻的位置、环境、在场角色与可去之处。"""
    lines = [f"当前舞台：{stage_name}", f"环境：{environment}", "", "在场角色："]
    lines.extend(f"- {actor}" for actor in actors)
    lines.extend(["", "可去之处："])
    lines.extend(f"- {item}" for item in exits)
    lines.extend(
        [
            "",
            "用工具表达你这一轮的行动：说话、移动，或者原地不动。一次只做一件事。",
        ]
    )
    return "\n".join(lines)


############################################################################################################
@final
class ActorPlanSystem(ReactiveProcessor, SystemMixin):
    """消费 ``ActorPlanAction``：对每个待计划的角色跑一轮 agent loop。"""

    ##########################################################################################
    def __init__(self, game: SRPGGame) -> None:
        ReactiveProcessor.__init__(self, game)
        SystemMixin.__init__(self, game)

    ##########################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(all_of=[ActorPlanAction, ActorComponent]): GroupEvent.ADDED}

    ##########################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        """只处理仍挂着动作的角色。"""
        return entity.has(ActorComponent, ActorPlanAction)

    ##########################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        for entity in sorted(entities, key=lambda item: item.index):
            await self._plan(entity)

    ##########################################################################################
    async def _plan(self, entity: Entity) -> None:
        try:
            result = await agent_loop(
                name=f"plan:{entity.name}",
                input_message=self._input_message(entity),
                messages=get_agent_memory(self._game, entity).messages,
                tools=_PLAN_TOOLS,
                handlers=_plan_handlers(entity),
                max_rounds=_PLAN_ROUNDS,
                terminal_tools=_PLAN_TOOLS,
                loop_id=f"plan:{entity.name}",
            )
        except Exception as e:
            # 计划是可选的一步：失败就当这个角色本轮轮空，不能拖垮整条 pipeline
            logger.opt(exception=e).warning(
                f"[plan:{entity.name}] 计划失败，本轮轮空: {type(e).__name__}: {e}"
            )
            return

        logger.info(
            " ".join(
                [
                    f"[plan:{entity.name}]",
                    f"success={result.success}",
                    f"rounds={len(result.rounds)}",
                    f"tools={_called_tools(result)}",
                ]
            )
        )

    ##########################################################################################
    def _input_message(self, entity: Entity) -> str:
        stage_name = entity.get(ActorComponent).current_stage
        stage_entity = get_stage_entity(self._game, stage_name)
        assert (
            stage_entity is not None
        ), f"角色 {entity.name} 的所在舞台不存在: {stage_name}"
        return actor_plan_prompt(
            stage_name=stage_name,
            environment=_environment_of(stage_entity),
            actors=[
                _describe_actor(actor)
                for actor in sorted(
                    get_actors_in_stage(self._game, entity),
                    key=lambda item: item.index,
                )
            ],
            exits=[_describe_exit(exit_) for exit_ in get_exits(self._game, entity)],
        )


############################################################################################################
def _plan_handlers(
    actor: Entity,
) -> Dict[str, Callable[..., Union[str, Awaitable[str]]]]:
    """本轮的「行为」表：每个工具都是往角色身上挂一个动作。"""

    def speak(content: str) -> str:
        return _mount(actor, ActorSpeakAction, content)

    def move(x: int, y: int) -> str:
        return _mount(actor, ActorMoveAction, x, y)

    def wait() -> str:
        return _mount(actor, ActorWaitAction)

    return {"speak": speak, "move": move, "wait": wait}


############################################################################################################
def _mount(actor: Entity, action_type: Type[Component], *args: object) -> str:
    """把动作挂到角色身上；本轮已经有行动时忽略后到的，回执里说明。"""
    if any(actor.has(item) for item in _BEHAVIOUR_ACTIONS):
        logger.warning(f"[plan:{actor.name}] 本轮已有行动，忽略 {action_type.__name__}")
        return "（本轮已经有行动了，这次忽略）"
    actor.replace(action_type, *args)
    logger.info(f"[plan:{actor.name}] {action_type.__name__}{args}")
    return "（已记下）"


############################################################################################################
def _called_tools(result: AgentLoopResult) -> str:
    """本次计划实际调用了哪些工具；一个都没有时明说，免得和「调了一个」混在一起。"""
    names = [
        call.function.name
        for one_round in result.rounds
        for call in (one_round.completion.tool_calls or [])
    ]
    return ",".join(names) if names else "无"


############################################################################################################
def _environment_of(stage_entity: Entity) -> str:
    if not stage_entity.has(EnvironmentComponent):
        return _NO_ENVIRONMENT
    return stage_entity.get(EnvironmentComponent).narrative


############################################################################################################
def _describe_exit(exit_: Exit) -> str:
    """一格一行：坐标，以及那格上是空地还是某个据点。"""
    where = exit_.stage if exit_.stage is not None else "空地"
    return f"({exit_.x},{exit_.y}) {where}"


############################################################################################################
def _describe_actor(actor: Entity) -> str:
    """一行一个角色；外观是它此刻的样子，没有就只给名字。"""
    if not actor.has(AppearanceComponent):
        return actor.name
    return f"{actor.name}：{actor.get(AppearanceComponent).appearance}"


############################################################################################################
__all__ = ["ActorPlanSystem", "actor_plan_prompt"]
