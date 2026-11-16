"""TurnEndArbitrationSystem 单元测试。"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_dbg.deepseek import LOOP_END_ATTR, LOOP_ID_ATTR, AgentLoopResult
from ai_dbg.entitas.context import Context
from ai_dbg.entitas.entity import Entity
from ai_dbg.game.memory import REPLACED_MESSAGES_ATTR
from ai_dbg.models import (
    ActorComponent,
    AIMessage,
    Card,
    CombatRoundComponent,
    CombatState,
    HandComponent,
    HumanMessage,
    PassTurnAction,
    RoundEntryKind,
    SystemMessage,
    TargetType,
)
from ai_dbg.systems import arbitration_common
from ai_dbg.systems.turn_end_arbitration_system import TurnEndArbitrationSystem
from dungeon_support import (
    current_round_entity,
    install_combat,
    set_combat_state,
)


def _make_card(name: str, *, turn_end: bool = False) -> Card:
    return Card(
        name=name,
        description="测试卡牌",
        on_turn_end_affixes=["[灼烧]:回合结束时对持有者造成伤害"] if turn_end else [],
        playable=not turn_end,
        retain=turn_end,
        damage=1,
        hit_count=1,
        target_type=TargetType.SELF,
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
    install_combat(game)
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


class TestCollectHandTurnEndCards:
    def test_returns_only_turn_end_cards(
        self, context: Context, mock_game: Any
    ) -> None:
        system = TurnEndArbitrationSystem(mock_game)
        actor = _make_actor(context, "英雄")
        actor.get(HandComponent).cards.extend(
            [
                _make_card("普通牌"),
                _make_card("灼纹", turn_end=True),
                _make_card("另一张普通牌"),
            ]
        )

        cards = system._collect_hand_turn_end_cards(actor)

        assert [c.name for c in cards] == ["灼纹"]


class TestTurnEndArbitrationSystem:
    def test_filter_requires_pass_turn_action(
        self, context: Context, mock_game: Any
    ) -> None:
        system = TurnEndArbitrationSystem(mock_game)
        entity = context.create_entity()
        assert system.filter(entity) is False

        entity.add(PassTurnAction, "英雄")
        assert system.filter(entity) is True

    @pytest.mark.asyncio
    async def test_react_skips_when_not_ongoing(
        self, context: Context, mock_game: Any
    ) -> None:
        set_combat_state(mock_game, CombatState.COMPLETE)
        system = TurnEndArbitrationSystem(mock_game)
        entity = context.create_entity()
        entity.add(PassTurnAction, "英雄")

        with patch(
            "ai_dbg.systems.turn_end_arbitration_system.agent_loop"
        ) as mock_agent_loop:
            await system.react([entity])

        mock_agent_loop.assert_not_called()

    @pytest.mark.asyncio
    async def test_react_skips_when_no_turn_end_cards(
        self, context: Context, mock_game: Any
    ) -> None:
        system = TurnEndArbitrationSystem(mock_game)
        pass_entity = _make_actor(context, "英雄")
        pass_entity.add(PassTurnAction, "英雄")
        pass_entity.get(HandComponent).cards.append(_make_card("普通牌"))

        with patch(
            "ai_dbg.systems.turn_end_arbitration_system.agent_loop"
        ) as mock_agent_loop:
            await system.react([pass_entity])

        mock_agent_loop.assert_not_called()

    @pytest.mark.asyncio
    async def test_stage_arbitrates_turn_end(
        self, context: Context, mock_game: Any
    ) -> None:
        system = TurnEndArbitrationSystem(mock_game)
        holder = _make_actor(context, "怪物.纸人")
        holder.add(PassTurnAction, "怪物.纸人")
        holder.get(HandComponent).cards.append(_make_card("灼纹", turn_end=True))

        with patch(
            "ai_dbg.systems.turn_end_arbitration_system.agent_loop",
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
            "turn_end:1:怪物.纸人#"
        )
        # 提示词已写死目标恒为持有者
        assert (
            "目标恒为持有者本人 怪物.纸人"
            in mock_agent_loop.await_args.kwargs["input_message"]
        )
        # 未提交结果（mock 未驱动 handler）：不回滚，只补一条「未完成」系统说明
        mock_game.replace_span.assert_not_called()
        mock_game.add_human_message.assert_called_once()
        notice = mock_game.add_human_message.call_args.args[1]
        assert "本次结算未完成" in notice.content
        assert "未落库" in notice.content

        entries = current_round_entity(mock_game).get(CombatRoundComponent).entries
        assert entries[0].kind == RoundEntryKind.FAILED


class TestTurnEndLoopMemoryCompression:
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
    async def test_success_compresses_loop_span_into_summary(
        self, context: Context, mock_game: Any
    ) -> None:
        system = TurnEndArbitrationSystem(mock_game)
        holder = _make_actor(context, "怪物.纸人")
        holder.add(PassTurnAction, "怪物.纸人")
        holder.get(HandComponent).cards.append(_make_card("灼纹", turn_end=True))

        with patch(
            "ai_dbg.systems.turn_end_arbitration_system.agent_loop",
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
        assert "本次回合结束无 HP 变化" in summary.content
        assert getattr(summary, LOOP_ID_ATTR).startswith("turn_end:1:怪物.纸人#")
        assert getattr(summary, LOOP_END_ATTR) == getattr(summary, LOOP_ID_ATTR)
