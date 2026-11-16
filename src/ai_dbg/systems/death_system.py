"""死亡处理系统：HP 归零即标记死亡；若死者是当前行动者则重算回合指针。"""

from typing import Final, final, override

from loguru import logger

from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.combat import (
    compute_character_stats,
    get_current_turn_actor,
    mark_dead,
)
from ..game.combat.state import set_round_current_actor
from ..game.context import DBGGame
from ..game.dungeon import (
    current_combat_round_entity,
    current_dungeon_combat,
    is_current_room_dungeon_combat,
)
from ..game.memory import (
    add_human_message,
)
from ..models import (
    CharacterStatsComponent,
    CombatRoundComponent,
    DeathComponent,
    HumanMessage,
)
from ..utils import prompt_builder


###############################################################################################################################################
@prompt_builder
def _build_death_notification() -> str:
    """生成角色 HP 归零失去战斗能力的通知文本。"""
    return "# 你的HP已归零，失去战斗能力！"


###############################################################################################################################################
@final
class DeathSystem(ExecuteProcessor):
    """
    死亡处理系统：将 HP 归零且尚未标记死亡的实体标记为死亡。
    """

    ############################################################################################################
    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ############################################################################################################
    @override
    async def execute(self) -> None:
        defeated_entities = self._game.ecs.get_group(
            Matcher(all_of=[CharacterStatsComponent], none_of=[DeathComponent])
        ).entities.copy()

        for entity in defeated_entities:
            entity_hp = compute_character_stats(entity).hp
            if entity_hp <= 0:
                logger.info(f"{entity.name} 已被击败，HP={entity_hp}")
                add_human_message(
                    self._game,
                    entity,
                    HumanMessage(
                        content=_build_death_notification(),
                        death_notification=entity.name,
                    ),
                )
                mark_dead(entity)
                self._advance_turn_if_current(entity)

    ############################################################################################################
    def _advance_turn_if_current(self, entity: Entity) -> None:
        """若刚死亡的是本回合当前行动者，则重算回合指针以跳过它，避免回合卡死。

        回合指针只在过牌时推进，而过牌会拒绝死亡角色；因此「当前行动者在自己回合内死亡」
        （反伤自杀 / 神器后仲裁等）会导致无人能推进。此处补一次重算，让 `get_current_turn_actor`
        的「跳过死人」逻辑生效。
        """
        if not is_current_room_dungeon_combat(self._game):
            return
        if not current_dungeon_combat(self._game).is_ongoing:
            return
        latest_round_entity = current_combat_round_entity(self._game)
        if latest_round_entity is None:
            return
        latest_round = latest_round_entity.get(CombatRoundComponent)
        if latest_round.current_actor != entity.name:
            return
        next_actor = get_current_turn_actor(self._game, latest_round)
        set_round_current_actor(latest_round_entity, next_actor)
        logger.info(
            f"DeathSystem: 当前行动者 {entity.name} 死亡，回合指针推进为 {next_actor}"
        )
