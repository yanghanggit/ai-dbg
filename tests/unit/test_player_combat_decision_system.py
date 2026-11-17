"""`PlayerCombatDecisionSystem` 单测：玩家的决策记录与怪物侧同构，原因用占位句。

玩家的决策来自外部指令，计算端没有决策 LLM，所以本系统只写记录、不做推理：
形状对齐（做了什么 + 目标 + 原因），原因留占位——与怪物侧决策记录同构。
"""

import json
from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from ai_dbg.entitas import GroupEvent
from ai_dbg.entitas.entity import Entity
from ai_dbg.game.context import ECSContext
from ai_dbg.models import (
    ActorComponent,
    Card,
    CombatState,
    DeathComponent,
    HandComponent,
    HumanMessage,
    MonsterComponent,
    PassTurnAction,
    PlayCardsAction,
    PlayerComponent,
    TargetType,
)
from ai_dbg.systems.combat_decision_common import (
    ACTION_PLAY,
    REASON_PLACEHOLDER,
    UNPLAYABLE_CAUSE,
    build_combat_decision_tag,
)
from ai_dbg.systems.player_combat_decision_system import PlayerCombatDecisionSystem
from dungeon_support import (
    append_combat_round,
    install_combat,
    set_combat_state,
)


def _make_card() -> Card:
    return Card(
        name="攻击",
        description="",
        cost=1,
        damage=5,
        hit_count=1,
        target_type=TargetType.SINGLE,
        source="角色.无名",
    )


def _make_actor(
    context: ECSContext, name: str, *, player: bool = True, dead: bool = False
) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "场景.河湾芦苇丛")
    entity.add(HandComponent, name, [])
    if player:
        entity.add(PlayerComponent, name)
    else:
        entity.add(MonsterComponent, name)
    if dead:
        entity.add(DeathComponent, name)
    return entity


@pytest.fixture()
def context() -> ECSContext:
    return ECSContext()


@pytest.fixture()
def game(context: ECSContext) -> Any:
    mock = MagicMock()
    mock.ecs = context
    mock.world.agent_memories = {}
    mock.events = MagicMock()
    install_combat(
        mock,
        action_order=["角色.无名"],
        current_actor="角色.无名",
    )
    return mock


def _records(game: Any) -> List[Any]:
    return [
        message
        for memory in game.world.agent_memories.values()
        for message in memory.messages
        if getattr(message, "combat_decision", None) is not None
    ]


class TestPlayerDecisionRecord:
    async def test_play_writes_same_shape_as_monster(
        self, context: ECSContext, game: Any
    ) -> None:
        actor = _make_actor(context, "角色.无名")
        card = _make_card()
        actor.get(HandComponent).cards.append(card)
        actor.add(PlayCardsAction, actor.name, card, ["怪物.渡口野狗"])

        await PlayerCombatDecisionSystem(game).react([actor])

        records = _records(game)
        assert len(records) == 1
        content = records[0].content
        assert content.splitlines()[0] == "# 第 1 回合 · 你的行动"
        assert "你打出了「攻击」。" in content
        assert "目标：怪物.渡口野狗。" in content
        assert f"原因：{REASON_PLACEHOLDER}" in content

        tag: Dict[str, Any] = json.loads(records[0].combat_decision)
        assert tag == {
            "round": 1,
            "action": "play",
            "card": "攻击",
            "targets": ["怪物.渡口野狗"],
            "reason": REASON_PLACEHOLDER,
            "forced": False,
        }

    async def test_pass_writes_pass_record(
        self, context: ECSContext, game: Any
    ) -> None:
        actor = _make_actor(context, "角色.无名")
        actor.add(PassTurnAction, actor.name)

        await PlayerCombatDecisionSystem(game).react([actor])

        records = _records(game)
        assert len(records) == 1
        assert "你选择不出牌，直接过牌。" in records[0].content
        assert json.loads(records[0].combat_decision)["action"] == "pass"

    async def test_unplayable_card_records_blocked_play(
        self, context: ECSContext, game: Any
    ) -> None:
        """结算层会拦下不可出的牌，记录必须同步：本想打、没打出去（与怪物侧同形）。"""
        actor = _make_actor(context, "角色.无名")
        card = _make_card().model_copy(update={"playable": False})
        actor.get(HandComponent).cards.append(card)
        actor.add(PlayCardsAction, actor.name, card, ["怪物.渡口野狗"])

        await PlayerCombatDecisionSystem(game).react([actor])

        records = _records(game)
        assert len(records) == 1
        content = records[0].content
        assert "你本想打出「攻击」" in content
        assert f"但{UNPLAYABLE_CAUSE}" in content
        assert "因此这次出牌没有发生" in content
        assert f"原因：{REASON_PLACEHOLDER}" in content

        tag: Dict[str, Any] = json.loads(records[0].combat_decision)
        assert tag["action"] == "pass"
        assert tag["card"] == "攻击"
        assert tag["targets"] == []
        assert tag["forced"] is True

    async def test_pass_after_play_is_not_recorded_again(
        self, context: ECSContext, game: Any
    ) -> None:
        """出完牌后交出行动权是机械步骤，不是第二次决策：不再写一条「不出牌」。"""
        actor = _make_actor(context, "角色.无名")
        actor.add(PassTurnAction, actor.name)
        game.world.agent_memories[actor.name] = SimpleNamespace(
            messages=[
                HumanMessage(
                    content="# 第 1 回合 · 你的行动\n你打出了「攻击」。",
                    combat_decision=build_combat_decision_tag(
                        1,
                        ACTION_PLAY,
                        card_name="攻击",
                        targets=["怪物.渡口野狗"],
                        reason=REASON_PLACEHOLDER,
                        forced=False,
                    ),
                )
            ]
        )

        await PlayerCombatDecisionSystem(game).react([actor])

        assert len(_records(game)) == 1

    async def test_pass_in_a_new_round_is_still_recorded(
        self, context: ECSContext, game: Any
    ) -> None:
        """上一回合出过牌不影响本回合：本回合只过牌，就是一次真的过牌决策。"""
        append_combat_round(game)
        actor = _make_actor(context, "角色.无名")
        actor.add(PassTurnAction, actor.name)
        game.world.agent_memories[actor.name] = SimpleNamespace(
            messages=[
                HumanMessage(
                    content="# 第 1 回合 · 你的行动\n你打出了「攻击」。",
                    combat_decision=build_combat_decision_tag(
                        1,
                        ACTION_PLAY,
                        card_name="攻击",
                        targets=["怪物.渡口野狗"],
                        reason=REASON_PLACEHOLDER,
                        forced=False,
                    ),
                )
            ]
        )

        await PlayerCombatDecisionSystem(game).react([actor])

        records = _records(game)
        assert len(records) == 2
        assert "你选择不出牌，直接过牌。" in records[-1].content
        assert json.loads(records[-1].combat_decision)["round"] == 2

    async def test_skips_when_combat_not_ongoing(
        self, context: ECSContext, game: Any
    ) -> None:
        set_combat_state(game, CombatState.COMPLETE)
        actor = _make_actor(context, "角色.无名")
        actor.add(PassTurnAction, actor.name)

        await PlayerCombatDecisionSystem(game).react([actor])

        assert len(_records(game)) == 0

    def test_filter_requires_player_and_liveness(
        self, context: ECSContext, game: Any
    ) -> None:
        system = PlayerCombatDecisionSystem(game)
        alive_player = _make_actor(context, "角色.无名")
        alive_player.add(PassTurnAction, alive_player.name)
        dead_player = _make_actor(context, "角色.坏运气", dead=True)
        dead_player.add(PassTurnAction, dead_player.name)
        monster = _make_actor(context, "怪物.渡口野狗", player=False)
        monster.add(PassTurnAction, monster.name)

        assert system.filter(alive_player)
        assert not system.filter(dead_player)
        assert not system.filter(monster)

    def test_triggers_on_both_decision_actions(
        self, context: ECSContext, game: Any
    ) -> None:
        """出牌与过牌共用同一触发集合（怪物侧两种决策都会记录）。"""
        triggers = PlayerCombatDecisionSystem(game).get_trigger()
        assert len(triggers) == 2
        assert set(triggers.values()) == {GroupEvent.ADDED}
