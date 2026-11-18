"""战斗回合开始系统：按有效速度确定行动顺序，开启一个新回合。"""

import random
from enum import StrEnum, unique
from typing import Dict, Final, List, Optional, Set, final, override

from loguru import logger

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.combat import (
    compute_character_stats,
    get_alive_actors_in_stage,
)
from ..game.combat.state import (
    combat_rounds,
    combat_turns,
    current_combat_round,
    latest_combat_round,
)
from ..game.context import SRPGGame
from ..game.dungeon import (
    current_combat_entity,
    current_dungeon_combat,
    is_current_room_dungeon_combat,
)
from ..game.entities import (
    create_entity,
    get_entity_by_name,
    get_player_entity,
    resolve_stage_entity,
)
from ..models import (
    CharacterStatsComponent,
    CombatRoundComponent,
    CombatTurnComponent,
    CombatTurnStatus,
    CurrentCombatRoundComponent,
    CurrentCombatTurnComponent,
    DrawCardsAction,
    DungeonComponent,
    IdentityComponent,
)
from .combat_turn_state import CombatTurnStateMixin


###############################################################################################################################################
# 行动顺序策略枚举
@final
@unique
class ActionOrderStrategy(StrEnum):
    """战斗回合中角色行动顺序的排序策略"""

    SPEED = "speed"  # 按速度降序（默认；速度相同按实体创建顺序升序）
    RANDOM = "random"  # 随机打乱（测试用）
    CREATION_ORDER = (
        "creation_order"  # 按实体创建顺序（creation_order 小的靠前，测试用）
    )


############################################################################################################
def _combat_round_entity_name(combat_name: str, index: int) -> str:
    return f"{combat_name}#round-{index}"


############################################################################################################
def _combat_turn_entity_name(round_name: str, order_index: int) -> str:
    return f"{round_name}#turn-{order_index}"


############################################################################################################
@final
class CombatRoundStartSystem(ReactiveProcessor, CombatTurnStateMixin):
    """
    战斗回合开始系统：监听 DrawCardsAction，在需要时创建并开启新回合。

    必须在 DrawCardsActionSystem 之前注册（顺序即因果链：先开回合，后抓牌）。
    """

    ############################################################################################################
    def __init__(
        self,
        game: SRPGGame,
        strategy: ActionOrderStrategy = ActionOrderStrategy.SPEED,
    ) -> None:
        super().__init__(game.ecs)
        self._game: SRPGGame = game
        self._strategy: Final[ActionOrderStrategy] = strategy

    ############################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        """监听 DrawCardsAction 的添加事件，作为创建新回合的唯一触发源。"""
        return {Matcher(DrawCardsAction): GroupEvent.ADDED}

    ############################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(DrawCardsAction)

    ############################################################################################################
    def _create_round(
        self,
        combat_entity: Entity,
        *,
        index: int,
        action_order: List[str],
        current_actor: Optional[str],
    ) -> Entity:
        """创建新回合及其行动槽，并把它标记为当前回合。"""
        existing_round = current_combat_round(self._game, combat_entity)
        if existing_round is not None:
            existing_round.remove(CurrentCombatRoundComponent)
            for turn_entity in combat_turns(self._game, existing_round):
                if turn_entity.has(CurrentCombatTurnComponent):
                    turn_entity.remove(CurrentCombatTurnComponent)

        round_name = _combat_round_entity_name(combat_entity.name, index)
        assert (
            get_entity_by_name(self._game, round_name) is None
        ), f"回合实体已存在: {round_name}"

        round_entity = create_entity(self._game, round_name)
        round_entity.replace(
            CombatRoundComponent,
            round_name,
            combat_entity.name,
            index,
            False,
            False,
        )
        round_entity.replace(CurrentCombatRoundComponent, round_name)

        for order_index, actor_name in enumerate(action_order, start=1):
            self._create_turn(
                round_entity,
                actor_name=actor_name,
                order_index=order_index,
            )

        if current_actor is not None:
            current_turn = next(
                (
                    turn_entity
                    for turn_entity in combat_turns(self._game, round_entity)
                    if turn_entity.get(CombatTurnComponent).actor_name == current_actor
                ),
                None,
            )
            assert (
                current_turn is not None
            ), f"行动顺序中没有当前行动者: {current_actor}"
            self._set_current_turn(current_turn)

        return round_entity

    ############################################################################################################
    def _create_turn(
        self,
        round_entity: Entity,
        *,
        actor_name: str,
        order_index: int,
    ) -> Entity:
        """创建回合内的一个行动槽实体。"""
        round_comp = round_entity.get(CombatRoundComponent)
        turn_name = _combat_turn_entity_name(round_entity.name, order_index)
        assert (
            get_entity_by_name(self._game, turn_name) is None
        ), f"行动槽实体已存在: {turn_name}"

        turn_entity = create_entity(self._game, turn_name)
        turn_entity.replace(
            CombatTurnComponent,
            turn_name,
            round_comp.combat_name,
            round_entity.name,
            actor_name,
            order_index,
            CombatTurnStatus.PENDING,
            2,
        )
        return turn_entity

    ############################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        if not is_current_room_dungeon_combat(self._game):
            return
        logger.debug(
            f"CombatRoundStartSystem: 收到 {len(entities)} 个 DrawCardsAction 实体"
        )

        # 状态守卫①：战斗未进行中 → 静默跳过
        if not current_dungeon_combat(self._game).is_ongoing:
            logger.debug("当前战斗状态非 ONGOING，跳过回合创建")
            return

        # 状态守卫②：已有进行中的回合（未完成）→ 不重复创建
        combat_entity = current_combat_entity(self._game)
        latest_round = latest_combat_round(self._game, combat_entity)
        if (
            latest_round is not None
            and not latest_round.get(CombatRoundComponent).is_completed
        ):
            logger.debug("当前已有未完成回合，跳过回合创建")
            return

        logger.debug("DrawCardsAction 触发，开始创建新回合...")

        # 玩家角色
        player_entity = get_player_entity(self._game)
        assert player_entity is not None, "player_entity is None"

        # 所有存活角色
        actors_in_stage = get_alive_actors_in_stage(self._game, player_entity)
        assert len(actors_in_stage) > 0, "actors_in_stage is empty"
        for actor in actors_in_stage:
            assert actor.has(
                CharacterStatsComponent
            ), f"actor {actor.name} 缺少 CharacterStatsComponent"
            assert actor.has(
                IdentityComponent
            ), f"actor {actor.name} 缺少 IdentityComponent"

        # 当前舞台（必须是副本）
        stage_entity = resolve_stage_entity(self._game, player_entity)
        assert stage_entity is not None, "stage_entity is None"
        assert stage_entity.has(DungeonComponent), "stage_entity 没有 DungeonComponent"

        round_number = len(combat_rounds(self._game, combat_entity)) + 1

        match self._strategy:
            case ActionOrderStrategy.RANDOM:
                snapshot_entities = self._shuffled_actors_by_round(actors_in_stage)
            case ActionOrderStrategy.CREATION_ORDER:
                snapshot_entities = self._sorted_actors_by_creation_order(
                    actors_in_stage
                )
            case _:  # SPEED（默认；含未知策略回退）
                snapshot_entities = self._sorted_actors_by_speed(actors_in_stage)

        action_order = [entity.name for entity in snapshot_entities]
        current_actor = snapshot_entities[0].name if snapshot_entities else None
        self._create_round(
            combat_entity,
            index=round_number,
            action_order=action_order,
            current_actor=current_actor,
        )
        logger.debug(f"设置当前 turn 行动角色: {current_actor}")
        logger.info(f"创建第 {round_number} 回合，行动顺序: {action_order}")

    ############################################################################################################
    def _shuffled_actors_by_round(self, actors: Set[Entity]) -> List[Entity]:
        """把本回合参战角色随机打乱顺序。"""
        eligible: List[Entity] = list(actors)
        random.shuffle(eligible)
        return eligible

    ############################################################################################################
    def _sorted_actors_by_creation_order(self, actors: Set[Entity]) -> List[Entity]:
        """把本回合参战角色按创建顺序升序排列。"""
        eligible: List[Entity] = list(actors)
        eligible.sort(key=lambda entity: entity.get(IdentityComponent).creation_order)
        return eligible

    ############################################################################################################
    def _sorted_actors_by_speed(self, actors: Set[Entity]) -> List[Entity]:
        """把本回合参战角色按有效速度降序排列；速度相同按创建顺序升序（先创建先出手）。"""
        eligible: List[Entity] = list(actors)
        eligible.sort(
            key=lambda entity: (
                -compute_character_stats(entity).speed,
                entity.get(IdentityComponent).creation_order,
            )
        )
        return eligible

    ################################################################################################################
