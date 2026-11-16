"""出牌系统：消耗能量、拦截不可出牌、广播行动预告，效果结算交给仲裁。"""

from typing import Dict, Final, List, final

from loguru import logger
from overrides import override

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.combat import (
    consume_turn_energy,
    get_current_turn_actor,
)
from ..game.context import DBGGame
from ..game.dungeon import (
    current_combat_turn_entity,
    current_dungeon_combat,
    is_current_room_dungeon_combat,
)
from ..game.entities import (
    resolve_stage_entity,
)
from ..game.memory import (
    add_human_message,
)
from ..game.messaging import (
    broadcast_to_stage,
)
from ..models import (
    ActorComponent,
    HandComponent,
    HumanMessage,
    NoneEvent,
    PlayCardsAction,
)
from ..utils import prompt_builder
from .combat_decision_common import play_blocked_cause


#######################################################################################################################################
@prompt_builder
def _build_action_notice_for_others(actor_name: str, round_number: int) -> str:
    """生成出牌行动预告，广播给场景内其他角色，维护观察者视角的叙事连贯性。"""
    return f"【第 {round_number} 回合】{actor_name} 正在出牌。"


#######################################################################################################################################
@prompt_builder
def _build_unplayable_card_error_message(actor_name: str, card_name: str) -> str:
    """构建不可出牌卡牌的拦截提示（写入出牌者上下文，供 LLM 下次决策参考）。"""
    return f"""# 提示！{actor_name} 试图打出「{card_name}」，但该卡牌不可出牌（playable=False）。

**提示：** playable=False 的卡牌不能出牌，只能留在手牌中（如带回合结束词缀的卡牌），下一次决策时请不要选择它。"""


#######################################################################################################################################
@final
class PlayCardsActionSystem(ReactiveProcessor):
    """出牌动作系统。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game.ecs)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(PlayCardsAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(PlayCardsAction)
            and entity.has(HandComponent)
            and entity.has(ActorComponent)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        """处理出牌动作。"""
        if not is_current_room_dungeon_combat(self._game):
            return
        if not current_dungeon_combat(self._game).is_ongoing:
            # 必须是 进行中的阶段！
            logger.debug("PlayCardsActionSystem: 战斗未进行中，跳过出牌处理")
            return

        assert len(entities) == 1, "PlayCardsActionSystem: 一次只能处理一个出牌动作实体"
        logger.debug(
            f"PlayCardsActionSystem: 触发出牌处理，找到 {len(entities)} 个出牌实体"
        )

        # 获取当前回合数
        current_rounds = current_dungeon_combat(self._game).rounds
        assert (
            current_rounds is not None
        ), "PlayCardsActionSystem: current_rounds is None"

        last_round = current_dungeon_combat(self._game).latest_round
        assert last_round is not None, "PlayCardsActionSystem: latest_round is None"

        logger.debug(
            f"PlayCardsActionSystem: 当前回合数 {len(current_rounds)}，最新回合状态: {'已完成' if last_round.is_completed else '未完成'}"
        )

        for entity in entities:

            # 输出出牌信息日志，包含角色名、卡牌名、卡牌属性（治疗/攻击/防御）和目标
            play_cards_action = entity.get(PlayCardsAction)

            # 计算端拦截：不可出牌的卡（playable=False）不进入出牌流程，防止 LLM 决策误选。
            # 判定与措辞复用 `play_blocked_cause`：决策记录层用同一口径，记忆才不会与结算矛盾。
            blocked_cause = play_blocked_cause(play_cards_action.card)
            if blocked_cause:
                logger.error(
                    f"PlayCardsActionSystem: 卡牌 '{play_cards_action.card.name}' 被拦下：{blocked_cause}（playable=False），拦截出牌"
                )
                # 将拦截原因写入出牌者上下文，让 LLM 下次决策时理解
                add_human_message(
                    self._game,
                    entity=entity,
                    human_message=HumanMessage(
                        content=_build_unplayable_card_error_message(
                            play_cards_action.name,
                            play_cards_action.card.name,
                        ),
                        unplayable_card=play_cards_action.card.name,
                    ),
                )
                entity.remove(PlayCardsAction)
                continue

            logger.debug(
                f"  [{play_cards_action.name}] 出牌 → 卡牌: {play_cards_action.card.name} | damage={play_cards_action.card.damage} | 目标: {play_cards_action.targets}"
            )

            # 写一个assert 要求 entity.name 必须是当前回合的行动者
            assert entity.name == get_current_turn_actor(
                self._game, last_round
            ), f"PlayCardsActionSystem: 出牌角色 {entity.name} 不是当前 turn 的行动者！ current_turn_actor={get_current_turn_actor(self._game, last_round)}"

            # 每出一张牌消耗当前行动槽的 energy 点数（出牌本身不视为"完成行动"，
            # 仅 pass turn 才会把行动槽标记为 completed 并真正交出行动权，
            # 见 PassTurnActionSystem；因此这里不推进当前行动槽。）
            current_turn_entity = current_combat_turn_entity(self._game)
            assert (
                current_turn_entity is not None
            ), "PlayCardsActionSystem: 当前行动槽不存在"
            consume_turn_energy(current_turn_entity, play_cards_action.card.cost)

            logger.debug(
                f"  completed_actors: {last_round.completed_actors} / current_turn_actor_name={last_round.current_actor}"
            )

            # 行动类广播：出牌者已有决策记录（`combat_decision`）作为更精确的自我记录，故排除自己；
            # 其余人（含场景外？不，仅本场景）在仲裁结算前先感知到出牌事件
            stage_entity = resolve_stage_entity(self._game, entity)
            assert (
                stage_entity is not None
            ), f"PlayCardsActionSystem: 无法找到 {entity.name} 所在的场景实体"
            broadcast_to_stage(
                self._game,
                entity=entity,
                agent_event=NoneEvent(
                    message=_build_action_notice_for_others(
                        actor_name=play_cards_action.name,
                        round_number=len(current_rounds),
                    )
                ),
                exclude_entities={entity, stage_entity},
            )
