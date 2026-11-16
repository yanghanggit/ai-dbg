"""AutonomousArbitrationSystem 单元测试。

验证自主运行词缀（`on_autonomous_affixes`）：
- 触发于 pass turn，但**不锁定持有者**——目标可为场上任意存活角色；
- 紧跟回合结束仲裁之后（独立系统，规则单一）；
- 成功结算后写 `RoundEntryKind.AUTONOMOUS` 记录。
"""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_dbg.deepseek import LOOP_END_ATTR, LOOP_ID_ATTR, AgentLoopResult
from ai_dbg.entitas.context import Context
from ai_dbg.entitas.entity import Entity
from ai_dbg.game.dungeon import (
    current_dungeon_combat_room,
)
from ai_dbg.game.memory import REPLACED_MESSAGES_ATTR
from ai_dbg.models import (
    ActorComponent,
    AIMessage,
    Card,
    HandComponent,
    HumanMessage,
    PassTurnAction,
    RoundEntryKind,
    SystemMessage,
    TargetType,
)
from ai_dbg.systems import arbitration_common
from ai_dbg.systems.autonomous_arbitration_system import (
    AutonomousArbitrationSystem,
)


def _make_card(name: str, *, autonomous: bool = False) -> Card:
    return Card(
        name=name,
        description="测试卡牌",
        on_autonomous_affixes=(
            ["[自主]:每回合对一名敌人造成本卡 damage 的伤害"] if autonomous else []
        ),
        playable=not autonomous,
        retain=autonomous,
        damage=1,
        hit_count=1,
        target_type=TargetType.SINGLE,
    )


def _make_actor(context: Context, name: str) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "场景.测试密室")
    entity.add(HandComponent, name, [])
    return entity


@pytest.fixture()
def context() -> Context:
    return Context()


@pytest.fixture()
def mock_game(context: Context, monkeypatch: pytest.MonkeyPatch) -> Any:
    game = MagicMock()
    game.ecs = context
    game.entity_index = {}
    game.world.agent_memories = {
        "场景.测试密室": SimpleNamespace(
            messages=[SystemMessage(content="你是本场景的仲裁者")]
        )
    }
    game.player_session = MagicMock()
    combat: Any = current_dungeon_combat_room(game).combat
    combat.is_ongoing = True
    combat.rounds = [MagicMock()]
    stage = context.create_entity()
    stage._name = "场景.测试密室"
    from ai_dbg.models import StageComponent

    stage.add(StageComponent, stage.name)

    real_add: Any = getattr(arbitration_common, "add_human_message")
    game.add_human_message = MagicMock(
        side_effect=lambda entity, message: real_add(game, entity, message)
    )
    monkeypatch.setattr(
        arbitration_common,
        "add_human_message",
        lambda _game, entity, message: game.add_human_message(entity, message),
    )
    real_replace: Any = getattr(arbitration_common, "replace_span")
    game.replace_span = MagicMock(
        side_effect=lambda entity, start, end, messages, **kwargs: real_replace(
            game, entity, start, end, messages, **kwargs
        )
    )
    monkeypatch.setattr(
        arbitration_common,
        "replace_span",
        lambda _game, entity, start, end, messages, **kwargs: game.replace_span(
            entity, start, end, messages, **kwargs
        ),
    )
    return game


class TestCollectHandAutonomousCards:
    def test_returns_only_autonomous_cards(
        self, context: Context, mock_game: Any
    ) -> None:
        system = AutonomousArbitrationSystem(mock_game)
        actor = _make_actor(context, "英雄")
        actor.get(HandComponent).cards.extend(
            [
                _make_card("普通牌"),
                _make_card("召唤兽", autonomous=True),
                _make_card("另一张普通牌"),
            ]
        )

        cards = system._collect_hand_autonomous_cards(actor)

        assert [c.name for c in cards] == ["召唤兽"]


class TestAutonomousArbitrationSystem:
    def test_filter_requires_pass_turn_and_autonomous_card(
        self, context: Context, mock_game: Any
    ) -> None:
        system = AutonomousArbitrationSystem(mock_game)
        entity = context.create_entity()
        assert system.filter(entity) is False

        entity.add(PassTurnAction, "英雄")
        assert system.filter(entity) is False

        entity.add(HandComponent, "英雄", [_make_card("召唤兽", autonomous=True)])
        assert system.filter(entity) is True

    def test_filter_false_when_no_autonomous_card(
        self, context: Context, mock_game: Any
    ) -> None:
        system = AutonomousArbitrationSystem(mock_game)
        holder = _make_actor(context, "英雄")
        holder.add(PassTurnAction, "英雄")
        holder.get(HandComponent).cards.append(_make_card("普通牌"))

        assert system.filter(holder) is False

    @pytest.mark.asyncio
    async def test_react_skips_when_not_ongoing(
        self, context: Context, mock_game: Any
    ) -> None:
        cast(Any, current_dungeon_combat_room(mock_game)).combat.is_ongoing = False
        system = AutonomousArbitrationSystem(mock_game)
        holder = _make_actor(context, "英雄")
        holder.add(PassTurnAction, "英雄")
        holder.get(HandComponent).cards.append(_make_card("召唤兽", autonomous=True))

        with patch(
            "ai_dbg.systems.autonomous_arbitration_system.agent_loop"
        ) as mock_agent_loop:
            await system.react([holder])

        mock_agent_loop.assert_not_called()

    @pytest.mark.asyncio
    async def test_stage_arbitrates_autonomous_without_locking_target(
        self, context: Context, mock_game: Any
    ) -> None:
        system = AutonomousArbitrationSystem(mock_game)
        holder = _make_actor(context, "怪物.纸人")
        holder.add(PassTurnAction, "怪物.纸人")
        holder.get(HandComponent).cards.append(_make_card("召唤兽", autonomous=True))

        with patch(
            "ai_dbg.systems.autonomous_arbitration_system.agent_loop",
            new=AsyncMock(
                return_value=AgentLoopResult(
                    success=False, start_index=0, end_index=0, messages=[]
                )
            ),
        ) as mock_agent_loop:
            await system.react([holder])

        assert mock_agent_loop.await_count == 1
        assert mock_agent_loop.await_args is not None
        # 仲裁者是所在场景，不是持有者本人
        assert mock_agent_loop.await_args.kwargs["name"] == "场景.测试密室"
        # 携带唯一的 loop_id 标记
        assert mock_agent_loop.await_args.kwargs["loop_id"].startswith(
            "autonomous:1:怪物.纸人#"
        )
        # 提示词明确「目标可为场上任意存活角色」，且不锁定持有者
        prompt = mock_agent_loop.await_args.kwargs["input_message"]
        assert "场上任意存活角色" in prompt
        assert "不锁定持有者" in prompt
        # 未提交结果（mock 未驱动 handler）：不回滚，只补一条「未完成」系统说明
        mock_game.replace_span.assert_not_called()
        mock_game.add_human_message.assert_called_once()
        notice = mock_game.add_human_message.call_args.args[1]
        assert "本次结算未完成" in notice.content
        assert "未落库" in notice.content

        latest_round: Any = current_dungeon_combat_room(mock_game).combat.latest_round
        assert latest_round.record.call_args.args[0] == RoundEntryKind.FAILED


class TestAutonomousLoopMemoryCompression:
    def _fake_success(self, **kwargs: Any) -> AgentLoopResult:
        messages = kwargs["messages"]
        start = len(messages)
        messages.append(
            HumanMessage(content=kwargs["input_message"], loop_id=kwargs["loop_id"])
        )
        kwargs["handlers"]["submit_arbitration"](
            combat_log="", narrative="叙事文本", summary="本次压缩总结"
        )
        messages.append(AIMessage(content="工具完成"))
        return AgentLoopResult(
            success=True,
            start_index=start,
            end_index=len(messages),
            messages=messages,
            start_message=messages[start],
        )

    @pytest.mark.asyncio
    async def test_success_compresses_span_and_records_autonomous(
        self, context: Context, mock_game: Any
    ) -> None:
        system = AutonomousArbitrationSystem(mock_game)
        holder = _make_actor(context, "怪物.纸人")
        holder.add(PassTurnAction, "怪物.纸人")
        holder.get(HandComponent).cards.append(_make_card("召唤兽", autonomous=True))

        with patch(
            "ai_dbg.systems.autonomous_arbitration_system.agent_loop",
            new=AsyncMock(side_effect=self._fake_success),
        ):
            await system.react([holder])

        # 整段 loop 记忆被压缩为一条 HumanMessage
        assert mock_game.replace_span.call_count == 1
        _, start_index, end_index, new_messages = mock_game.replace_span.call_args.args
        assert (start_index, end_index) == (1, 3)
        assert (
            mock_game.replace_span.call_args.kwargs["dump_attr"]
            == REPLACED_MESSAGES_ATTR
        )
        assert len(new_messages) == 1
        summary = new_messages[0]
        assert isinstance(summary, HumanMessage)
        assert "本次压缩总结" in summary.content
        assert getattr(summary, LOOP_ID_ATTR).startswith("autonomous:1:怪物.纸人#")
        assert getattr(summary, LOOP_END_ATTR) == getattr(summary, LOOP_ID_ATTR)

        # 落库写入独立的 AUTONOMOUS 回合记录
        latest_round: Any = current_dungeon_combat_room(mock_game).combat.latest_round
        assert latest_round.record.call_count == 1
        assert latest_round.record.call_args.args[0] == RoundEntryKind.AUTONOMOUS
