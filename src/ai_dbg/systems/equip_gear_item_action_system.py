"""装备转化系统模块：将 GearItem 的 cards 直接物化为多张 Card 放入当前行动者手牌。"""

from dataclasses import dataclass
from typing import Dict, Final, List, final
from uuid import uuid4

from overrides import override

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.combat import compute_character_stats
from ..game.combat.state import record_round_entry
from ..game.context import DBGGame
from ..game.dungeon import (
    current_combat_round_entity,
    current_combat_turn_entity,
    current_dungeon_combat,
    is_current_room_dungeon_combat,
)
from ..game.entities import (
    get_actor_entity,
    get_player_entity,
    resolve_stage_entity,
)
from ..game.messaging import broadcast_to_stage
from ..models import (
    Card,
    CombatTurnComponent,
    EquipGearItemAction,
    EquippedGearComponent,
    GearItem,
    HandComponent,
    InventoryComponent,
    NoneEvent,
    PartyMemberComponent,
    RoundEntryKind,
    apply_stats_to_card,
)
from ..utils import prompt_builder


#######################################################################################################################################
@prompt_builder
def _build_gear_notice(
    actor_name: str,
    item_name: str,
    card_names: List[str],
    round_number: int,
) -> str:
    """生成装备转化广播通知。"""
    cards_str = "、".join(card_names)
    return f"【第 {round_number} 回合 · 装备行动】\n「{actor_name}」将「{item_name}」转化为手牌「{cards_str}」。"


#######################################################################################################################################
@dataclass(frozen=True)
class _EquipContext:
    """一次装备使用请求所需的战斗上下文。"""

    actor: Entity
    player: Entity


#######################################################################################################################################
@final
class EquipGearItemActionSystem(ReactiveProcessor):
    """装备转化系统：把团队背包内的 GearItem 物化为 Card 放入当前行动者手牌。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game.ecs)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(EquipGearItemAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(EquipGearItemAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        context = self._resolve_context()

        for request_entity in entities:
            action = request_entity.get(EquipGearItemAction)
            self._execute_request(context, action)

    ####################################################################################################################################
    def _resolve_context(self) -> _EquipContext:
        """校验战斗阶段与当前行动者，并定位团队背包持有者。"""

        if not is_current_room_dungeon_combat(self._game):
            raise ValueError("装备使用失败：当前副本房间不是战斗房间")

        combat = current_dungeon_combat(self._game)
        if not combat.is_ongoing:
            raise ValueError("装备使用失败：战斗未在进行中")

        latest_round = combat.latest_round
        if latest_round is None:
            raise ValueError("装备使用失败：当前没有进行中的回合")
        if latest_round.is_completed:
            raise ValueError("装备使用失败：当前回合已结束")
        if not latest_round.draw_completed:
            raise ValueError("装备使用失败：抽牌阶段尚未完成")

        current_turn_entity = current_combat_turn_entity(self._game)
        if current_turn_entity is None:
            raise ValueError("装备使用失败：当前没有行动角色")
        turn_comp = current_turn_entity.get(CombatTurnComponent)

        actor_entity = get_actor_entity(self._game, turn_comp.actor_name)
        if actor_entity is None:
            raise ValueError(
                f"装备使用失败：找不到当前行动角色 {turn_comp.actor_name}"
            )
        if not actor_entity.has(PartyMemberComponent):
            raise ValueError(
                f"装备使用失败：当前行动角色 {actor_entity.name} 不是我方角色"
            )
        if not actor_entity.has(HandComponent):
            raise ValueError(
                f"装备使用失败：当前行动角色 {actor_entity.name} 缺少手牌组件（HandComponent）"
            )

        player_entity = get_player_entity(self._game)
        if player_entity is None:
            raise ValueError("装备使用失败：玩家实体不存在")
        if not player_entity.has(InventoryComponent):
            raise ValueError("装备使用失败：玩家实体缺少 InventoryComponent")

        return _EquipContext(actor=actor_entity, player=player_entity)

    ####################################################################################################################################
    def _execute_request(
        self,
        context: _EquipContext,
        action: EquipGearItemAction,
    ) -> None:
        """执行一次装备使用请求。"""

        gear = self._find_gear(context.player, action.item_name)
        cards = self._materialize_cards(context.actor, gear)
        if not cards:
            raise ValueError(f"装备使用失败：装备 '{gear.name}' 没有可转化卡牌")

        self._move_gear_to_actor(context, gear)
        self._add_cards_to_hand(context.actor, cards)
        self._record_gear_use(context.actor, gear, cards)
        self._broadcast_gear_use(context.actor, gear, cards)

    ####################################################################################################################################
    def _find_gear(self, player: Entity, item_name: str) -> GearItem:
        """从团队背包中查找并校验指定装备。"""

        inventory = player.get(InventoryComponent)
        selected_item = next(
            (item for item in inventory.items if item.name == item_name),
            None,
        )
        if selected_item is None:
            raise ValueError(f"装备使用失败：玩家背包中找不到装备 '{item_name}'")
        if not isinstance(selected_item, GearItem):
            raise ValueError(
                f"装备使用失败：物品 '{item_name}' 不是装备（类型: {type(selected_item).__name__}）"
            )
        return selected_item

    ####################################################################################################################################
    def _move_gear_to_actor(self, context: _EquipContext, gear: GearItem) -> None:
        """把装备从团队背包移动到当前行动者的已装备列表。"""

        player = context.player
        actor = context.actor

        inventory = player.get(InventoryComponent)
        player.replace(
            InventoryComponent,
            inventory.name,
            [item for item in inventory.items if item is not gear],
        )

        if actor.has(EquippedGearComponent):
            equipped = actor.get(EquippedGearComponent)
            actor.replace(
                EquippedGearComponent,
                equipped.name,
                [*equipped.items, gear],
            )
        else:
            actor.replace(EquippedGearComponent, actor.name, [gear])

    ####################################################################################################################################
    def _add_cards_to_hand(self, actor: Entity, cards: List[Card]) -> None:
        """把物化出的卡牌追加到当前行动者手牌。"""

        hand_comp = actor.get(HandComponent)
        actor.replace(HandComponent, hand_comp.name, [*hand_comp.cards, *cards])

    ####################################################################################################################################
    def _record_gear_use(
        self,
        actor: Entity,
        gear: GearItem,
        cards: List[Card],
    ) -> None:
        """记录本回合的装备使用结果。"""

        round_entity = current_combat_round_entity(self._game)
        if round_entity is None:
            return

        card_names = [card.name for card in cards]
        record_round_entry(
            self._game,
            round_entity,
            RoundEntryKind.GEAR,
            f"[{actor.name} 装备 {gear.name}] 生成手牌「{'、'.join(card_names)}」",
            "；".join(card.description for card in cards),
        )

    ####################################################################################################################################
    def _broadcast_gear_use(
        self,
        actor: Entity,
        gear: GearItem,
        cards: List[Card],
    ) -> None:
        """向场景内其他角色广播装备转化结果。"""

        round_number = len(current_dungeon_combat(self._game).rounds)
        stage_entity = resolve_stage_entity(self._game, actor)
        assert (
            stage_entity is not None
        ), f"EquipGearItemActionSystem: 无法找到 {actor.name} 所在的场景实体"

        broadcast_to_stage(
            self._game,
            entity=actor,
            agent_event=NoneEvent(
                message=_build_gear_notice(
                    actor.name,
                    gear.name,
                    [card.name for card in cards],
                    round_number,
                )
            ),
            exclude_entities={stage_entity},
        )

    ####################################################################################################################################
    def _materialize_cards(
        self,
        entity: Entity,
        gear: GearItem,
    ) -> List[Card]:
        """将 GearItem.cards 复制物化为多张手牌 Card，并叠加当前行动者属性加成。"""

        actor_stats = compute_character_stats(entity)

        cards: List[Card] = []
        for spec in gear.cards:
            card = spec.model_copy(deep=True)
            # 手牌是一张独立副本，必须重新生成 uuid（exhaust/discard 系统按 uuid 定位）
            card.uuid = str(uuid4())
            card.source = entity.name
            # 计算端强制：GearItem 转化的卡牌跨回合保留在手牌（不进入弃牌堆）
            card.retain = True

            # 沿用 fill_draw_pile_system 的思路：卡牌自身值非 0 时，叠加当前行动者属性
            apply_stats_to_card(card, actor_stats)

            cards.append(card)

        return cards
