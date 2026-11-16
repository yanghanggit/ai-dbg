"""副本实体销毁模块

负责销毁副本相关实体（敌人、场景、房间、副本），是 setup_dungeon 的逆操作。
"""

from loguru import logger

from ..game.combat.state import (
    destroy_combat,
    get_combat_entity_for_room,
)
from ..game.context import DBGGame
from ..game.dungeon import (
    dungeon_rooms,
    get_dungeon_entity,
)
from ..game.entities import (
    destroy_entity,
    get_actors_in_stage,
)
from ..models import CombatComponent, MonsterComponent


###################################################################################################################################################################
def teardown_dungeon(dbg_game: DBGGame) -> None:
    """销毁副本相关实体，是 setup_dungeon 的逆操作。"""

    dungeon_entity = get_dungeon_entity(dbg_game)
    if dungeon_entity is None:
        logger.debug("[teardown_dungeon] 当前没有副本实体，跳过")
        return

    logger.debug(
        f"[teardown_dungeon] 开始清理副本实体: dungeon={dungeon_entity.name!r}"
    )
    rooms = dungeon_rooms(dbg_game)

    # 1. 销毁所有房间场景中的怪物实体（队伍成员此时应已传送回大厅）
    for room_entity in rooms:
        for actor_entity in get_actors_in_stage(dbg_game, room_entity):
            if actor_entity.has(MonsterComponent):
                destroy_entity(dbg_game, actor_entity)

    # 2. 销毁房间对应的战斗实体，再销毁 Stage 实体
    for room_entity in rooms:
        if room_entity.has(CombatComponent):
            destroy_combat(
                dbg_game,
                get_combat_entity_for_room(dbg_game, room_entity),
            )
        destroy_entity(dbg_game, room_entity)

    # 3. 销毁副本实体
    destroy_entity(dbg_game, dungeon_entity)

    logger.debug("[teardown_dungeon] 副本实体清理完成")
