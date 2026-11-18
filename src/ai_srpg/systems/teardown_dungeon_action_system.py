"""销毁副本实体系统：响应退出副本成功后的 TeardownDungeonAction。"""

from typing import Dict, Final, List, final

from loguru import logger
from overrides import override

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.combat.state import (
    combat_rounds,
    combat_turns,
    get_combat_entity_for_room,
)
from ..game.context import SRPGGame
from ..game.dungeon import dungeon_rooms, get_dungeon_entity
from ..game.entities import destroy_entity, get_actors_in_stage
from ..models import (
    CombatComponent,
    CurrentCombatRoundComponent,
    CurrentCombatTurnComponent,
    MonsterComponent,
    TeardownDungeonAction,
)


###################################################################################################################################################################
@final
class TeardownDungeonActionSystem(ReactiveProcessor):
    """销毁副本相关实体，是副本 setup 的逆操作。"""

    def __init__(self, game: SRPGGame) -> None:
        super().__init__(game.ecs)
        self._game: Final[SRPGGame] = game

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
                self._destroy_combat(
                    get_combat_entity_for_room(self._game, room_entity),
                )
            destroy_entity(self._game, room_entity)

        destroy_entity(self._game, dungeon_entity)
        logger.debug("[TeardownDungeonActionSystem] 副本实体清理完成")

    ####################################################################################################################################
    def _destroy_combat(self, combat_entity: Entity) -> None:
        """销毁战斗实体及其全部回合/行动槽实体，并解除房间上的战斗标记。"""
        for round_entity in combat_rounds(self._game, combat_entity):
            for turn_entity in combat_turns(self._game, round_entity):
                if turn_entity.has(CurrentCombatTurnComponent):
                    turn_entity.remove(CurrentCombatTurnComponent)
                destroy_entity(self._game, turn_entity)

            if round_entity.has(CurrentCombatRoundComponent):
                round_entity.remove(CurrentCombatRoundComponent)
            destroy_entity(self._game, round_entity)

        room_entities = self._game.ecs.get_group(
            Matcher(all_of=[CombatComponent])
        ).entities.copy()
        for room_entity in room_entities:
            combat_comp = room_entity.get(CombatComponent)
            if combat_comp.combat_name == combat_entity.name:
                room_entity.remove(CombatComponent)

        destroy_entity(self._game, combat_entity)
