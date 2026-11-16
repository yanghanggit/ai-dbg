"""过牌系统：交出行动权并清空剩余能量，是回合推进的唯一依据。"""

from typing import Dict, Final, List, final

from loguru import logger
from overrides import override

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.combat import (
    consume_energy,
    get_current_turn_actor,
    get_energy,
)
from ..game.combat.state import (
    append_round_completed_actor,
    set_round_current_actor,
)
from ..game.context import DBGGame
from ..game.dungeon import (
    current_combat_round_entity,
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
    CombatRoundComponent,
    HandComponent,
    NoneEvent,
    PassTurnAction,
    RoundStatsComponent,
)
from ..utils import prompt_builder


#######################################################################################################################################
@prompt_builder
def _build_pass_turn_notice(actor_name: str, round_number: int) -> str:
    """生成过牌通知，广播给场景内所有角色（含过牌者本人）。"""
    return f"【第 {round_number} 回合】{actor_name} 选择跳过出牌。"


#######################################################################################################################################
@final
class PassTurnActionSystem(ReactiveProcessor):
    """过牌动作系统。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game.ecs)
        self._game: Final[DBGGame] = game

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
            and entity.has(RoundStatsComponent)
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

        current_rounds = current_dungeon_combat(self._game).rounds
        assert (
            current_rounds is not None
        ), "PassTurnActionSystem: current_rounds is None"

        last_round_entity = current_combat_round_entity(self._game)
        assert (
            last_round_entity is not None
        ), "PassTurnActionSystem: latest_round_entity is None"
        last_round = last_round_entity.get(CombatRoundComponent)

        pass_turn_action = entity.get(PassTurnAction)
        logger.debug(f"  [{pass_turn_action.name}] 选择过牌（跳过出牌机会）")

        assert entity.name == get_current_turn_actor(
            self._game, last_round
        ), f"PassTurnActionSystem: 过牌角色 {entity.name} 不是当前 turn 的行动者！ current_turn_actor={get_current_turn_actor(self._game, last_round)}"

        # 消耗过牌角色的剩余全部行动能量（若有）；completed_actors 仅按 pass turn 决策次数追加一次，
        # 与 energy 是否耗尽无关——是否轮到下一角色完全由 completed_actors 决定（见 get_current_turn_actor）
        cur_energy = get_energy(entity)
        logger.debug(f"  {entity.name} 当前剩余行动能量: {cur_energy}，消耗后变为 0")
        if cur_energy > 0:
            consume_energy(entity, cur_energy)

        # 将过牌角色加入本回合已完成行动的角色列表，确保下一角色的回合判定正确
        append_round_completed_actor(last_round_entity, pass_turn_action.name)
        last_round = last_round_entity.get(CombatRoundComponent)

        # 结束当前角色的回合，进入下一角色的回合
        next_actor = get_current_turn_actor(self._game, last_round)
        set_round_current_actor(last_round_entity, next_actor)
        last_round = last_round_entity.get(CombatRoundComponent)
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
