"""动作的前置条件：一个动作做不做得了，只在这里判断一次。

计划（模型说出来）与接管（玩家下命令）走同一个入口，所以守卫必须共用一份判据——
否则玩家能瞬移、模型不能。system 用它决定做不做，CLI 用它做执行前预检。
"""

from typing import Any, Dict, Final, Optional, Tuple

from loguru import logger

from ...entitas import Entity
from ...entitas.components import Component
from ...models import (
    ActorEnterStageAction,
    ActorExitStageAction,
    ActorMoveWithinStageAction,
    ActorPlanAction,
    ActorSpeakAction,
    ActorTravelAction,
    ActorWaitAction,
)
from ..context import SRPGGame
from .queries import (
    get_adjacent_stages,
    get_cell,
    get_map_cells,
    get_settlement,
    get_stage_at_cell,
    get_stage_entity,
    is_on_map,
)

#: 动作 → 工具名：记忆里的工具调用与计划路径用同一套名字
_TOOL_NAMES: Final[Dict[type, str]] = {
    ActorSpeakAction: "speak",
    ActorTravelAction: "travel",
    ActorEnterStageAction: "enter",
    ActorExitStageAction: "exit",
    ActorMoveWithinStageAction: "move_within",
    ActorWaitAction: "wait",
}


############################################################################################################
def action_tool_call(action: Component) -> Tuple[str, Dict[str, Any]]:
    """动作在记忆里的样子：工具名 + 参数。接管写记忆时用它，与计划的工具调用同形。"""
    for action_type, tool_name in _TOOL_NAMES.items():
        if isinstance(action, action_type):
            return tool_name, _tool_arguments(action)
    raise ValueError(f"未知动作，无法写成工具调用: {type(action).__name__}")


############################################################################################################
def action_arguments(action: Component) -> Tuple[Any, ...]:
    """挂组件时的位置参数；与 ``Entity.replace`` 的字段顺序一致。"""
    return tuple(_tool_arguments(action).values())


############################################################################################################
def _tool_arguments(action: Component) -> Dict[str, Any]:
    if isinstance(action, ActorSpeakAction):
        return {"content": action.content}
    if isinstance(action, ActorTravelAction):
        return {"x": action.cell_x, "y": action.cell_y}
    if isinstance(action, ActorEnterStageAction):
        return {"stage": action.stage_name}
    if isinstance(action, ActorMoveWithinStageAction):
        return {"destination": action.destination}
    return {}


############################################################################################################
def action_blocker(
    srpg_game: SRPGGame, actor: Entity, action: Component
) -> Optional[str]:
    """这个动作此刻能否由这个角色执行；能做返回 ``None``，不能返回原因。"""
    if isinstance(action, ActorSpeakAction):
        return _block_local(srpg_game, actor, "战场上没有可说话的对象（地图不是场所）")
    if isinstance(action, ActorWaitAction):
        return None
    if isinstance(action, ActorTravelAction):
        return _block_travel(srpg_game, actor, action)
    if isinstance(action, ActorEnterStageAction):
        return _block_enter(srpg_game, actor, action)
    if isinstance(action, ActorExitStageAction):
        return _block_exit(srpg_game, actor)
    if isinstance(action, ActorMoveWithinStageAction):
        return _block_move_within(srpg_game, actor, action)
    if isinstance(action, ActorPlanAction):
        return None
    raise ValueError(f"未知动作，缺少守卫判据: {type(action).__name__}")


############################################################################################################
def _block_local(srpg_game: SRPGGame, actor: Entity, reason: str) -> Optional[str]:
    return reason if is_on_map(srpg_game, actor) else None


############################################################################################################
def _block_travel(
    srpg_game: SRPGGame, actor: Entity, action: ActorTravelAction
) -> Optional[str]:
    if not is_on_map(srpg_game, actor):
        return "只能站在战场上做战场移动"
    reachable = {(cell.x, cell.y) for cell in get_map_cells(srpg_game, actor)}
    target = (action.cell_x, action.cell_y)
    if target not in reachable:
        return f"只能移动到相邻格，目标 {target} 不在其中"
    return None


############################################################################################################
def _block_enter(
    srpg_game: SRPGGame, actor: Entity, action: ActorEnterStageAction
) -> Optional[str]:
    if not is_on_map(srpg_game, actor):
        return "已经不在战场上了"
    stage_entity = get_stage_entity(srpg_game, action.stage_name)
    if stage_entity is None:
        return f"没有这个据点: {action.stage_name}"
    global_stage, cell = get_cell(srpg_game, actor)
    here = get_stage_at_cell(srpg_game, global_stage, cell)
    if here is None or here.name != stage_entity.name:
        return f"不在 {stage_entity.name} 所在的格子 {cell}，进不去"
    return None


############################################################################################################
def _block_exit(srpg_game: SRPGGame, actor: Entity) -> Optional[str]:
    if get_settlement(srpg_game, actor) is None:
        return "已经站在战场上了，没有城可出"
    return None


############################################################################################################
def _block_move_within(
    srpg_game: SRPGGame, actor: Entity, action: ActorMoveWithinStageAction
) -> Optional[str]:
    if is_on_map(srpg_game, actor):
        return "站在战场上，没有城内可去的区域"
    reachable = {stage.name for stage in get_adjacent_stages(srpg_game, actor)}
    if action.destination not in reachable:
        logger.debug(f"{actor.name} 可去的相邻区域: {sorted(reachable)}")
        return f"据点内只能去相邻区域，目标 {action.destination!r} 不在其中"
    return None


###############################################################################
__all__ = ["action_arguments", "action_blocker", "action_tool_call"]
