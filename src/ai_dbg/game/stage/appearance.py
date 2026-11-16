"""Actor 外观查询模块。

提供 get_actor_appearances_in_stage 全局函数，用于获取场景内 Actor 的外观映射。
"""

from typing import Dict

from ...entitas import Entity, Matcher
from ...models import AppearanceComponent
from ..context import DBGGame
from ..entities import get_actors_in_stage


###############################################################################################################################################
def get_actor_appearances_in_stage(game: DBGGame, entity: Entity) -> Dict[str, str]:
    """获取场景上 Actor 的外观信息映射。"""
    ret: Dict[str, str] = {}
    for actor in get_actors_in_stage(
        game, entity, Matcher(all_of=[AppearanceComponent])
    ):
        final_appearance = actor.get(AppearanceComponent)
        ret.setdefault(final_appearance.name, final_appearance.appearance)
    return ret


###############################################################################################################################################
