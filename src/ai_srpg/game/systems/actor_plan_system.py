"""角色计划：让角色在一轮里先想清要做什么，用自己的话与工具表达。

计划是「想」而不是「做」：工具只打日志，世界状态不变，留下的痕迹只是角色记忆里这次
loop 的对话。谁能被计划由调用方决定——挂上 ``ActorPlanAction`` 即可；计划失败就当这个
角色本轮轮空，不抛给 pipeline。
"""

from typing import Awaitable, Callable, Dict, Final, List, Union, final, override

from loguru import logger

from ...deepseek import agent_loop
from ...entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ...llm import ToolDefinition, ToolFunction
from ...models import (
    ActorComponent,
    ActorPlanAction,
    AppearanceComponent,
    EnvironmentComponent,
)
from ...utils import prompt_builder
from ..context import SRPGGame
from ..entities.queries import get_actors_in_stage, get_stage_entity
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

_PLAN_TOOLS: Final[List[ToolDefinition]] = [_SPEAK_TOOL, _MOVE_TOOL]


############################################################################################################
@prompt_builder
def actor_plan_prompt(*, stage_name: str, environment: str, actors: List[str]) -> str:
    """计划任务说明：这一刻的舞台环境与在场角色。"""
    lines = [f"当前舞台：{stage_name}", f"环境：{environment}", "", "在场角色："]
    lines.extend(f"- {actor}" for actor in actors)
    lines.extend(["", "用工具表达你这一轮要做的行动；没有想做的事就直接结束。"])
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
                handlers=_plan_handlers(entity.name),
                max_rounds=_PLAN_ROUNDS,
                loop_id=f"plan:{entity.name}",
            )
        except Exception as e:
            # 计划是可选的一步：失败就当这个角色本轮轮空，不能拖垮整条 pipeline
            logger.opt(exception=e).warning(
                f"[plan:{entity.name}] 计划失败，本轮轮空: {type(e).__name__}: {e}"
            )
            return

        logger.info(
            f"[plan:{entity.name}] success={result.success} rounds={len(result.rounds)}"
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
        )


############################################################################################################
def _plan_handlers(
    actor_name: str,
) -> Dict[str, Callable[..., Union[str, Awaitable[str]]]]:
    """本轮的「行为」表；回执告诉模型已记下，免得它为同一件事反复调用。"""

    def speak(content: str) -> str:
        logger.info(f"[plan:{actor_name}] speak: {content}")
        return "（已记下，尚未生效）"

    def move(target: str) -> str:
        logger.info(f"[plan:{actor_name}] move: {target}")
        return "（已记下，尚未生效）"

    return {"speak": speak, "move": move}


############################################################################################################
def _environment_of(stage_entity: Entity) -> str:
    if not stage_entity.has(EnvironmentComponent):
        return _NO_ENVIRONMENT
    return stage_entity.get(EnvironmentComponent).narrative


############################################################################################################
def _describe_actor(actor: Entity) -> str:
    """一行一个角色；外观是它此刻的样子，没有就只给名字。"""
    if not actor.has(AppearanceComponent):
        return actor.name
    return f"{actor.name}：{actor.get(AppearanceComponent).appearance}"


############################################################################################################
__all__ = ["ActorPlanSystem", "actor_plan_prompt"]
