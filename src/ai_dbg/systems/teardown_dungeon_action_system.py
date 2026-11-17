"""销毁副本实体系统：响应退出副本成功后的 TeardownDungeonAction。"""

from typing import Dict, Final, List, final

from loguru import logger
from overrides import override

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.combat.state import destroy_combat, get_combat_entity_for_room
from ..game.context import DBGGame
from ..game.dungeon import dungeon_rooms, get_dungeon_entity
from ..game.entities import destroy_entity, get_actors_in_stage
from ..models import CombatComponent, MonsterComponent, TeardownDungeonAction


###################################################################################################################################################################
@final
class TeardownDungeonActionSystem(ReactiveProcessor):
    """销毁副本相关实体，是副本 setup 的逆操作。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game.ecs)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(TeardownDungeonAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(TeardownDungeonAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        if not entities:
            return
        self._teardown_dungeon()

    ####################################################################################################################################
    def _teardown_dungeon(self) -> None:
        """销毁副本相关实体。"""

        dungeon_entity = get_dungeon_entity(self._game)
        if dungeon_entity is None:
            logger.debug("[TeardownDungeonActionSystem] 当前没有副本实体，跳过")
            return

        logger.debug(
            f"[TeardownDungeonActionSystem] 开始清理副本实体: dungeon={dungeon_entity.name!r}"
        )
        rooms = dungeon_rooms(self._game)

        for room_entity in rooms:
            for actor_entity in get_actors_in_stage(self._game, room_entity):
                if actor_entity.has(MonsterComponent):
                    destroy_entity(self._game, actor_entity)

        for room_entity in rooms:
            if room_entity.has(CombatComponent):
                destroy_combat(
                    self._game,
                    get_combat_entity_for_room(self._game, room_entity),
                )
            destroy_entity(self._game, room_entity)

        destroy_entity(self._game, dungeon_entity)
        logger.debug("[TeardownDungeonActionSystem] 副本实体清理完成")
