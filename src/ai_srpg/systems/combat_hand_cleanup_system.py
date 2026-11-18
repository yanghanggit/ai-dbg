"""战斗手牌清理系统：回合完成或战斗结束时，统一结算所有角色的手牌。"""

from typing import Final, List, final, override

from loguru import logger

from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.context import SRPGGame
from ..game.dungeon import (
    current_dungeon_combat,
    is_current_room_dungeon_combat,
)
from ..models import (
    CombatView,
    DiscardPileComponent,
    DrawPileComponent,
    HandComponent,
)
from .card_pile_common import HandSettlement, record_round_end_discard


###############################################################################################################################################
@final
class CombatHandCleanupSystem(ExecuteProcessor):
    """战斗手牌清理系统：回合完成或战斗结束时，结算手牌并移除 HandComponent。"""

    def __init__(self, game: SRPGGame) -> None:
        self._game: Final[SRPGGame] = game

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:
        if not is_current_room_dungeon_combat(self._game):
            return

        combat = current_dungeon_combat(self._game)
        if not self._should_cleanup(combat):
            return

        logger.debug("结算回合末手牌")
        record_round_end_discard(
            self._game,
            self._settle_round_hands(),
        )

    ###############################################################################################################################################
    def _settle_round_hands(self) -> List[HandSettlement]:
        """结算当前所有带手牌角色的回合末手牌。"""

        entities = self._game.ecs.get_group(
            Matcher(all_of=[HandComponent, DiscardPileComponent, DrawPileComponent])
        ).entities.copy()
        return [self._settle_hand(entity) for entity in entities]

    ###############################################################################################################################################
    def _settle_hand(self, entity: Entity) -> HandSettlement:
        """结算单个角色的手牌：非 retain 进弃牌堆，retain 进下回合保留队列，然后移除手牌。"""

        hand_comp = entity.get(HandComponent)
        discard_pile_comp = entity.get(DiscardPileComponent)

        discarded = [card for card in hand_comp.cards if not card.retain]
        retained = [card for card in hand_comp.cards if card.retain]

        if discarded:
            entity.replace(
                DiscardPileComponent,
                discard_pile_comp.name,
                [*discard_pile_comp.cards, *discarded],
            )

        if retained:
            draw_pile_comp = entity.get(DrawPileComponent)
            entity.replace(
                DrawPileComponent,
                draw_pile_comp.name,
                draw_pile_comp.cards,
                [*draw_pile_comp.retained_cards, *retained],
            )

        entity.remove(HandComponent)
        return HandSettlement(
            owner=entity,
            discarded=tuple(discarded),
            retained=tuple(retained),
        )

    ###############################################################################################################################################
    def _should_cleanup(self, combat: CombatView) -> bool:
        """回合已完成，或战斗已结束时清理；战后阶段不再重复清理。"""

        if combat.is_combat_completed:
            return True
        if not combat.is_ongoing:
            return False

        latest_round = combat.latest_round
        return latest_round is not None and latest_round.is_completed
