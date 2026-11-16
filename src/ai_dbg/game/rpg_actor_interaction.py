"""Actor 交互验证模块。

提供 validate_actor_interaction 全局函数及其依赖的 InteractionError 枚举。
"""

from enum import IntEnum, unique
from typing import final

from ..entitas import Entity
from .dbg_game import DBGGame
from .game_entities import get_actor_entity, resolve_stage_entity


###############################################################################################################################################
@unique
@final
class InteractionError(IntEnum):
    """Actor 交互验证的错误类型枚举。

    用于表示 validate_actor_interaction 函数的验证结果。
    值为 NONE 表示验证通过，其他值表示具体的错误类型。
    """

    NONE = 0  # 无错误
    TARGET_NOT_FOUND = 1  # 目标未找到
    INITIATOR_NOT_IN_STAGE = 2  # 发起者不在场景中
    DIFFERENT_STAGES = 3  # 不在同一场景


###############################################################################################################################################
def validate_actor_interaction(
    game: DBGGame, initiator_entity: Entity, target_name: str
) -> InteractionError:
    """验证两个 Actor 之间是否可以进行交互。"""
    actor_entity = get_actor_entity(game, target_name)
    if actor_entity is None:
        return InteractionError.TARGET_NOT_FOUND

    current_stage_entity = resolve_stage_entity(game, initiator_entity)
    if current_stage_entity is None:
        return InteractionError.INITIATOR_NOT_IN_STAGE

    target_stage_entity = resolve_stage_entity(game, actor_entity)
    if target_stage_entity != current_stage_entity:
        return InteractionError.DIFFERENT_STAGES

    return InteractionError.NONE


###############################################################################################################################################
