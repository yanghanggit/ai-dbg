"""回合行动者、回合清理与战斗残留校验。"""

from typing import List, Optional, Tuple

from loguru import logger

from ...entitas import Entity, Matcher
from ...models import (
    Card,
    CombatRoundComponent,
    CombatRoundView,
    DeathComponent,
    DiscardPileComponent,
    DrawPileComponent,
    ExhaustPileComponent,
    HandComponent,
    RoundStatsComponent,
)
from ..context import DBGGame
from ..entities import get_actor_entity


def get_current_turn_actor(
    game: DBGGame,
    round: CombatRoundView | CombatRoundComponent,
) -> Optional[str]:
    """从回合快照中找出第一个尚未 pass turn 的角色名。"""
    if not round.action_order:
        return None

    completed = set(round.completed_actors)
    for actor_name in round.action_order:
        if actor_name in completed:
            continue
        actor_entity = get_actor_entity(game, actor_name)
        assert actor_entity is not None, f"无法找到角色实体: {actor_name}"
        if actor_entity.has(DeathComponent):
            continue
        return actor_name

    return None


def clear_round_state(game: DBGGame) -> List[Tuple[Entity, List[Card], List[Card]]]:
    """清除所有角色实体的每回合可变状态（手牌归入弃牌堆 + 回合动态属性）。

    返回每张手牌的去向 `(entity, 进弃牌堆, 进保留队列)`，供调用方写牌堆变更记忆。
    """

    settlements: List[Tuple[Entity, List[Card], List[Card]]] = []

    # 清除所有角色实体的手牌组件（STS 标准：回合末未出牌进弃牌堆）
    for entity in game.ecs.get_group(
        Matcher(all_of=[HandComponent, DiscardPileComponent, DrawPileComponent])
    ).entities.copy():

        hand_comp = entity.get(HandComponent)
        discard_pile_comp = entity.get(DiscardPileComponent)
        discard_cards: List[Card] = []
        retain_cards: List[Card] = []

        if hand_comp.cards:

            retain_cards = [c for c in hand_comp.cards if c.retain]
            discard_cards = [c for c in hand_comp.cards if not c.retain]

            # 将非 retain 的手牌归入弃牌堆（战斗子堆均为副本，不会回流 DeckComponent）
            new_discard_cards = [*discard_pile_comp.cards, *discard_cards]
            entity.replace(
                DiscardPileComponent,
                discard_pile_comp.name,
                new_discard_cards,
            )

            # retain 牌暂存到 DrawPile 的保留队列，下回合优先取回手牌
            if retain_cards:
                assert entity.has(
                    DrawPileComponent
                ), f"{entity.name} 缺少 DrawPileComponent，无法存放 retain 牌"
                draw_pile_comp = entity.get(DrawPileComponent)
                entity.replace(
                    DrawPileComponent,
                    draw_pile_comp.name,
                    draw_pile_comp.cards,
                    [*draw_pile_comp.retained_cards, *retain_cards],
                )
                logger.debug(
                    f"clear hands: {entity.name} 将 {len(retain_cards)} 张 retain 牌转入 DrawPile 保留队列"
                )

            logger.debug(
                f"clear hands: {entity.name} 将 {len(discard_cards)} 张剩余手牌归入 DiscardPile，DiscardPile 累计 {len(new_discard_cards)} 张"
            )
        else:
            logger.debug(f"clear hands: {entity.name}")

        settlements.append((entity, discard_cards, retain_cards))

        # 无论是否有手牌，回合末统一移除 HandComponent
        entity.remove(HandComponent)

    # 清除所有角色实体的回合动态属性组件
    for entity in game.ecs.get_group(Matcher(RoundStatsComponent)).entities.copy():
        logger.debug(f"clear round stats: {entity.name}")
        entity.remove(RoundStatsComponent)

    return settlements


def assert_no_residual_combat_state(dbg_game: DBGGame) -> None:
    """断言战斗临时组件已被 pipeline（CombatRoundCleanupSystem/CombatOutcomeSystem/CombatPileTeardownSystem）清理干净，此函数不做任何清理动作。"""

    residual_entities = dbg_game.ecs.get_group(
        Matcher(
            any_of=[
                HandComponent,
                RoundStatsComponent,
                DrawPileComponent,
                DiscardPileComponent,
                ExhaustPileComponent,
            ]
        )
    ).entities

    assert (
        not residual_entities
    ), f"检测到残留战斗临时组件，pipeline 理应已清理完毕: {[entity.name for entity in residual_entities]}"
