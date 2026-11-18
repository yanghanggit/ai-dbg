"""过牌系统：交出行动权并清空剩余能量，是回合推进的唯一依据。"""

from typing import Dict, List, final

from loguru import logger
from overrides import override

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.combat import (
    consume_turn_energy,
    get_turn_energy,
)
from ..game.context import SRPGGame
from ..game.dungeon import (
    current_dungeon_combat,
    is_current_room_dungeon_combat,
)
from ..game.entities import (
    resolve_stage_entity,
)
from ..game.messaging import (
    broadcast_to_stage,
)
from ..models import (
    ActorComponent,
    CombatTurnComponent,
    CombatTurnStatus,
    HandComponent,
    NoneEvent,
    PassTurnAction,
)
from ..utils import prompt_builder
from .combat_pass_context import CombatPassContextMixin
from .combat_turn_state import CombatTurnStateMixin


#######################################################################################################################################
@prompt_builder
def _build_pass_turn_notice(actor_name: str, round_number: int) -> str:
    """生成过牌通知，广播给场景内所有角色（含过牌者本人）。"""
    return f"【第 {round_number} 回合】{actor_name} 选择跳过出牌。"


#######################################################################################################################################
@final
class PassTurnActionSystem(
    ReactiveProcessor, CombatPassContextMixin, CombatTurnStateMixin
):
    """过牌动作系统。"""

    def __init__(self, game: SRPGGame) -> None:
        super().__init__(game.ecs)
        self._game: SRPGGame = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(PassTurnAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(PassTurnAction)
            and entity.has(HandComponent)
            and entity.has(ActorComponent)
        )

    ####################################################################################################################################
    def _mark_turn_completed(self, turn_entity: Entity) -> None:
        """标记行动槽已完成（角色已过牌/交出行动权）。"""
        turn_comp = turn_entity.get(CombatTurnComponent)
        assert (
            turn_comp.status == CombatTurnStatus.PENDING
        ), f"只有待行动的行动槽可以完成: {turn_entity.name}"
        turn_entity.replace(
            CombatTurnComponent,
            turn_comp.name,
            turn_comp.combat_name,
            turn_comp.round_name,
            turn_comp.actor_name,
            turn_comp.order_index,
            CombatTurnStatus.COMPLETED,
            turn_comp.energy,
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        if not is_current_room_dungeon_combat(self._game):
            return
        if not current_dungeon_combat(self._game).is_ongoing:
            logger.debug("PassTurnActionSystem: 战斗未进行中，跳过过牌处理")
            return

        logger.debug("PassTurnActionSystem: 处理过牌动作实体")

        assert len(entities) == 1, "PassTurnActionSystem: 一次只能处理一个过牌动作实体"
        entity = entities[0]
        self._assert_pass_actor(entity.name)

        current_rounds = current_dungeon_combat(self._game).rounds
        assert (
            current_rounds is not None
        ), "PassTurnActionSystem: current_rounds is None"

        last_round_entity = self._pass_round()
        current_turn_entity = self._pass_turn()
        last_round = current_dungeon_combat(self._game).latest_round
        assert last_round is not None, "PassTurnActionSystem: latest_round is None"

        pass_turn_action = entity.get(PassTurnAction)
        logger.debug(f"  [{pass_turn_action.name}] 选择过牌（跳过出牌机会）")

        # 消耗过牌角色的剩余全部行动能量（若有）；是否轮到下一角色完全由行动槽状态决定。
        cur_energy = get_turn_energy(current_turn_entity)
        logger.debug(f"  {entity.name} 当前剩余行动能量: {cur_energy}，消耗后变为 0")
        if cur_energy > 0:
            consume_turn_energy(current_turn_entity, cur_energy)

        # 标记当前行动槽完成，并把行动权推进到下一个可用槽。
        self._mark_turn_completed(current_turn_entity)
        next_turn_entity = self._advance_current_turn(last_round_entity)
        next_actor = (
            next_turn_entity.get(CombatTurnComponent).actor_name
            if next_turn_entity is not None
            else None
        )
        last_round = current_dungeon_combat(self._game).latest_round
        assert (
            last_round is not None
        ), "PassTurnActionSystem: 刷新后 latest_round is None"
        logger.debug(f"advance_turn: current_turn_actor_name updated to {next_actor}")

        # 输出当前回合状态日志
        logger.debug(
            f"  completed_actors: {last_round.completed_actors} / current_turn_actor_name={last_round.current_actor}"
        )

        # 广播过牌通知给场景内所有角色（含过牌者本人），仅排除场景实体
        stage_entity = resolve_stage_entity(self._game, entity)
        assert (
            stage_entity is not None
        ), f"PassTurnActionSystem: 无法找到 {entity.name} 所在的场景实体"
        broadcast_to_stage(
            self._game,
            entity=entity,
            agent_event=NoneEvent(
                message=_build_pass_turn_notice(
                    actor_name=pass_turn_action.name,
                    round_number=len(current_rounds),
                )
            ),
            exclude_entities={stage_entity},
        )
