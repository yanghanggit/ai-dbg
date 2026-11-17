from typing import Any

"""CombatOutcomeSystem 单元测试。"""

from unittest.mock import MagicMock

import pytest

from ai_dbg.entitas.entity import Entity
from ai_dbg.game.context import ECSContext
from ai_dbg.game.dungeon import (
    current_combat_entity,
)
from ai_dbg.models import (
    ActorComponent,
    Card,
    CombatResult,
    CombatState,
    CombatStateComponent,
    DeathComponent,
    DiscardPileComponent,
    DrawPileComponent,
    ExhaustPileComponent,
    HandComponent,
    MonsterComponent,
    PartyMemberComponent,
    PlayerComponent,
    StageComponent,
)
from ai_dbg.systems.combat_outcome_system import CombatOutcomeSystem
from ai_dbg.systems.combat_result_notice_system import (
    CombatResultNoticeSystem,
    _build_combat_result_notification,
)
from dungeon_support import install_combat, set_combat_state

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_actor(
    context: ECSContext,
    name: str,
    *,
    is_ally: bool = False,
    is_monster: bool = False,
    is_dead: bool = False,
) -> Entity:
    """创建带阵营与死亡标记的参战角色实体。"""
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "stage")
    if is_ally:
        entity.add(PartyMemberComponent, name)
    if is_monster:
        entity.add(MonsterComponent, name)
    if is_dead:
        entity.add(DeathComponent, name)
    return entity


def _make_stage(context: ECSContext, name: str) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(StageComponent, name)
    return entity


def _make_card(name: str = "测试卡牌") -> Card:
    """创建一张占位卡牌。"""
    return Card(name=name, description="测试描述")


def _add_cards(
    entity: Entity,
    *,
    draw: int = 0,
    hand: int = 0,
    discard: int = 0,
    exhaust: int = 0,
) -> None:
    """为实体挂载牌堆组件并填入指定数量的占位卡牌。"""
    if draw:
        entity.add(
            DrawPileComponent,
            entity.name,
            [_make_card() for _ in range(draw)],
            [],
        )
    if hand:
        entity.add(HandComponent, entity.name, [_make_card() for _ in range(hand)])
    if discard:
        entity.add(
            DiscardPileComponent, entity.name, [_make_card() for _ in range(discard)]
        )
    if exhaust:
        entity.add(
            ExhaustPileComponent, entity.name, [_make_card() for _ in range(exhaust)]
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> ECSContext:
    """提供真实 ECS Context，保证组件操作正确生效。"""
    return ECSContext()


@pytest.fixture()
def mock_game(context: ECSContext) -> Any:
    """MagicMock DBGGame，预设战斗 ONGOING。"""
    game = MagicMock()
    game.ecs = context
    game.world.agent_memories = {}
    game.events = MagicMock()
    install_combat(game)
    return game


@pytest.fixture()
def system(mock_game: Any) -> CombatOutcomeSystem:
    return CombatOutcomeSystem(mock_game)


# ---------------------------------------------------------------------------
# Phase 1 — 纯函数测试
# ---------------------------------------------------------------------------


class TestGetCombatResultNotification:
    """_get_combat_result_notification 的单元测试。"""

    def test_victory_contains_victory_text(self) -> None:
        result = _build_combat_result_notification("黑暗副本", True)
        assert "胜利" in result

    def test_defeat_contains_defeat_text(self) -> None:
        result = _build_combat_result_notification("黑暗副本", False)
        assert "失败" in result

    def test_stage_name_in_output(self) -> None:
        result = _build_combat_result_notification("血色竞技场", True)
        assert "血色竞技场" in result


class TestCountAvailableCards:
    """_count_available_cards 的单元测试。"""

    def test_empty_entity_returns_zero(
        self, context: ECSContext, system: CombatOutcomeSystem
    ) -> None:
        entity = context.create_entity()
        assert system._count_available_cards(entity) == 0

    def test_counts_draw_hand_discard(
        self, context: ECSContext, system: CombatOutcomeSystem
    ) -> None:
        entity = context.create_entity()
        _add_cards(entity, draw=1, hand=2, discard=3)
        assert system._count_available_cards(entity) == 6

    def test_exhaust_pile_not_counted(
        self, context: ECSContext, system: CombatOutcomeSystem
    ) -> None:
        entity = context.create_entity()
        _add_cards(entity, exhaust=5)
        assert system._count_available_cards(entity) == 0


# ---------------------------------------------------------------------------
# Phase 2 — 阵营判定方法测试
# ---------------------------------------------------------------------------


class TestIsEnemySideEliminated:
    """_is_enemy_side_eliminated 的单元测试。"""

    def _setup(self, mock_game: Any, context: ECSContext, actors: set[Entity]) -> None:
        player = context.create_entity()
        player._name = "player"
        player.add(ActorComponent, "player", "stage")
        player.add(PlayerComponent, "player")
        stage = context.create_entity()
        stage._name = "stage"
        stage.add(StageComponent, "stage")
        for actor in actors:
            actor.replace(ActorComponent, actor.name, "stage")

    def test_no_enemies_returns_false(
        self, context: ECSContext, mock_game: Any, system: CombatOutcomeSystem
    ) -> None:
        """场景内无怪物时应返回 False。"""
        ally = _make_actor(context, "英雄", is_ally=True)
        self._setup(mock_game, context, {ally})
        assert system._is_enemy_side_eliminated() is False

    def test_alive_enemy_returns_false(
        self, context: ECSContext, mock_game: Any, system: CombatOutcomeSystem
    ) -> None:
        """有存活怪物时应返回 False。"""
        ally = _make_actor(context, "英雄", is_ally=True)
        monster = _make_actor(context, "哥布林", is_monster=True)
        self._setup(mock_game, context, {ally, monster})
        assert system._is_enemy_side_eliminated() is False

    def test_partial_elimination_returns_false(
        self, context: ECSContext, mock_game: Any, system: CombatOutcomeSystem
    ) -> None:
        """部分怪物死亡时应返回 False。"""
        ally = _make_actor(context, "英雄", is_ally=True)
        dead_monster = _make_actor(context, "哥布林", is_monster=True, is_dead=True)
        alive_monster = _make_actor(context, "巨魔", is_monster=True)
        self._setup(mock_game, context, {ally, dead_monster, alive_monster})
        assert system._is_enemy_side_eliminated() is False

    def test_all_enemies_dead_returns_true(
        self, context: ECSContext, mock_game: Any, system: CombatOutcomeSystem
    ) -> None:
        """全部怪物死亡时应返回 True。"""
        ally = _make_actor(context, "英雄", is_ally=True)
        dead1 = _make_actor(context, "哥布林", is_monster=True, is_dead=True)
        dead2 = _make_actor(context, "骷髅", is_monster=True, is_dead=True)
        self._setup(mock_game, context, {ally, dead1, dead2})
        assert system._is_enemy_side_eliminated() is True


class TestIsPlayerSideEliminated:
    """_is_player_side_eliminated 的单元测试。"""

    def _setup(self, mock_game: Any, context: ECSContext, actors: set[Entity]) -> None:
        player = context.create_entity()
        player._name = "player"
        player.add(ActorComponent, "player", "stage")
        player.add(PlayerComponent, "player")
        stage = context.create_entity()
        stage._name = "stage"
        stage.add(StageComponent, "stage")
        for actor in actors:
            actor.replace(ActorComponent, actor.name, "stage")

    def test_no_allies_returns_false(
        self, context: ECSContext, mock_game: Any, system: CombatOutcomeSystem
    ) -> None:
        """场景内无友方时应返回 False。"""
        monster = _make_actor(context, "哥布林", is_monster=True)
        self._setup(mock_game, context, {monster})
        assert system._is_player_side_eliminated() is False

    def test_alive_ally_returns_false(
        self, context: ECSContext, mock_game: Any, system: CombatOutcomeSystem
    ) -> None:
        """有存活友方时应返回 False。"""
        ally = _make_actor(context, "英雄", is_ally=True)
        monster = _make_actor(context, "哥布林", is_monster=True)
        self._setup(mock_game, context, {ally, monster})
        assert system._is_player_side_eliminated() is False

    def test_partial_elimination_returns_false(
        self, context: ECSContext, mock_game: Any, system: CombatOutcomeSystem
    ) -> None:
        """部分友方死亡时应返回 False。"""
        dead_ally = _make_actor(context, "英雄", is_ally=True, is_dead=True)
        alive_ally = _make_actor(context, "同伴", is_ally=True)
        monster = _make_actor(context, "哥布林", is_monster=True)
        self._setup(mock_game, context, {dead_ally, alive_ally, monster})
        assert system._is_player_side_eliminated() is False

    def test_all_allies_dead_returns_true(
        self, context: ECSContext, mock_game: Any, system: CombatOutcomeSystem
    ) -> None:
        """全部友方死亡时应返回 True。"""
        dead1 = _make_actor(context, "英雄", is_ally=True, is_dead=True)
        dead2 = _make_actor(context, "同伴", is_ally=True, is_dead=True)
        monster = _make_actor(context, "哥布林", is_monster=True)
        self._setup(mock_game, context, {dead1, dead2, monster})
        assert system._is_player_side_eliminated() is True


# ---------------------------------------------------------------------------
# Phase 3 — execute() 编排逻辑测试
# ---------------------------------------------------------------------------


class TestBothSidesCardless:
    """_is_both_sides_cardless 的单元测试。"""

    def _setup(self, mock_game: Any, context: ECSContext, actors: set[Entity]) -> None:
        player = context.create_entity()
        player._name = "player"
        player.add(ActorComponent, "player", "stage")
        player.add(PlayerComponent, "player")
        stage = context.create_entity()
        stage._name = "stage"
        stage.add(StageComponent, "stage")
        for actor in actors:
            actor.replace(ActorComponent, actor.name, "stage")

    def test_both_alive_cardless_returns_true(
        self, context: ECSContext, mock_game: Any, system: CombatOutcomeSystem
    ) -> None:
        """双方存活且均无可用卡牌时应返回 True。"""
        ally = _make_actor(context, "英雄", is_ally=True)
        monster = _make_actor(context, "哥布林", is_monster=True)
        self._setup(mock_game, context, {ally, monster})
        assert system._is_both_sides_cardless() is True

    def test_ally_has_cards_returns_false(
        self, context: ECSContext, mock_game: Any, system: CombatOutcomeSystem
    ) -> None:
        """仅友方有卡牌时应返回 False。"""
        ally = _make_actor(context, "英雄", is_ally=True)
        _add_cards(ally, discard=1)
        monster = _make_actor(context, "哥布林", is_monster=True)
        self._setup(mock_game, context, {ally, monster})
        assert system._is_both_sides_cardless() is False

    def test_enemy_has_cards_returns_false(
        self, context: ECSContext, mock_game: Any, system: CombatOutcomeSystem
    ) -> None:
        """仅敌方有卡牌时应返回 False。"""
        ally = _make_actor(context, "英雄", is_ally=True)
        monster = _make_actor(context, "哥布林", is_monster=True)
        _add_cards(monster, draw=1)
        self._setup(mock_game, context, {ally, monster})
        assert system._is_both_sides_cardless() is False

    def test_dead_member_cards_ignored(
        self, context: ECSContext, mock_game: Any, system: CombatOutcomeSystem
    ) -> None:
        """死亡成员的牌堆不计入可用卡牌：死亡友方仍有牌，但存活双方均无牌时应返回 True。"""
        dead_ally = _make_actor(context, "英雄", is_ally=True, is_dead=True)
        _add_cards(dead_ally, hand=3)
        alive_ally = _make_actor(context, "同伴", is_ally=True)
        monster = _make_actor(context, "哥布林", is_monster=True)
        self._setup(mock_game, context, {dead_ally, alive_ally, monster})
        assert system._is_both_sides_cardless() is True


class TestExecute:
    """CombatOutcomeSystem.execute() 的单元测试。"""

    def _setup(
        self,
        mock_game: Any,
        context: ECSContext,
        actors: set[Entity],
    ) -> Entity:
        """配置 mock_game 所需返回值，返回 stage_entity。"""
        player = context.create_entity()
        player._name = "player"
        player.add(ActorComponent, "player", "测试场景")
        player.add(PlayerComponent, "player")
        stage = _make_stage(context, "测试场景")
        for actor in actors:
            actor.replace(ActorComponent, actor.name, "测试场景")
        return stage

    @pytest.mark.asyncio
    async def test_skip_when_not_ongoing(
        self, context: ECSContext, mock_game: Any, system: CombatOutcomeSystem
    ) -> None:
        """战斗非 ONGOING 时，complete_combat 不应调用。"""
        set_combat_state(mock_game, CombatState.COMPLETE)
        await system.execute()
        assert (
            current_combat_entity(mock_game).get(CombatStateComponent).state
            == CombatState.COMPLETE
        )
        mock_game.add_human_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_result_when_both_sides_alive(
        self, context: ECSContext, mock_game: Any, system: CombatOutcomeSystem
    ) -> None:
        """双方均有存活且至少一方还有可用卡牌时，不应结束战斗。"""
        ally = _make_actor(context, "英雄", is_ally=True)
        _add_cards(ally, hand=1)
        monster = _make_actor(context, "哥布林", is_monster=True)
        self._setup(mock_game, context, {ally, monster})
        await system.execute()
        assert (
            current_combat_entity(mock_game).get(CombatStateComponent).result
            == CombatResult.NONE
        )

    @pytest.mark.asyncio
    async def test_both_sides_cardless_triggers_lose(
        self, context: ECSContext, mock_game: Any, system: CombatOutcomeSystem
    ) -> None:
        """双方均无可用卡牌时，应调用 complete_combat(LOSE)。"""
        ally = _make_actor(context, "英雄", is_ally=True)
        monster = _make_actor(context, "哥布林", is_monster=True)
        self._setup(mock_game, context, {ally, monster})
        await system.execute()
        assert (
            current_combat_entity(mock_game).get(CombatStateComponent).result
            == CombatResult.LOSE
        )

    @pytest.mark.asyncio
    async def test_enemy_eliminated_takes_priority_over_cardless(
        self, context: ECSContext, mock_game: Any, system: CombatOutcomeSystem
    ) -> None:
        """敌方全灭优先于卡牌耗尽：即使双方均无牌，敌方全灭仍应 WIN。"""
        ally = _make_actor(context, "英雄", is_ally=True)
        dead_monster = _make_actor(context, "哥布林", is_monster=True, is_dead=True)
        self._setup(mock_game, context, {ally, dead_monster})
        await system.execute()
        assert (
            current_combat_entity(mock_game).get(CombatStateComponent).result
            == CombatResult.WIN
        )

    @pytest.mark.asyncio
    async def test_enemy_eliminated_triggers_win(
        self, context: ECSContext, mock_game: Any, system: CombatOutcomeSystem
    ) -> None:
        """敌方全灭时应调用 complete_combat(WIN)。"""
        ally = _make_actor(context, "英雄", is_ally=True)
        dead_monster = _make_actor(context, "哥布林", is_monster=True, is_dead=True)
        self._setup(mock_game, context, {ally, dead_monster})
        await system.execute()
        assert (
            current_combat_entity(mock_game).get(CombatStateComponent).result
            == CombatResult.WIN
        )

    @pytest.mark.asyncio
    async def test_ally_eliminated_triggers_lose(
        self, context: ECSContext, mock_game: Any, system: CombatOutcomeSystem
    ) -> None:
        """友方全灭时应调用 complete_combat(LOSE)。"""
        dead_ally = _make_actor(context, "英雄", is_ally=True, is_dead=True)
        monster = _make_actor(context, "哥布林", is_monster=True)
        self._setup(mock_game, context, {dead_ally, monster})
        await system.execute()
        assert (
            current_combat_entity(mock_game).get(CombatStateComponent).result
            == CombatResult.LOSE
        )


# ---------------------------------------------------------------------------
# TestCombatOutcomeNotice — 胜负通知的阵营视角
# ---------------------------------------------------------------------------


class TestCombatOutcomeNotice:
    """胜负通知发给全部参战者，文本按各自视角生成。"""

    def _setup(self, context: ECSContext, mock_game: Any, actors: set[Entity]) -> None:
        player = context.create_entity()
        player._name = "player"
        player.add(ActorComponent, "player", "测试场景")
        player.add(PlayerComponent, "player")
        _make_stage(context, "测试场景")
        for actor in actors:
            actor.replace(ActorComponent, actor.name, "测试场景")

    async def _collect(
        self,
        context: ECSContext,
        mock_game: Any,
        actors: set[Entity],
    ) -> dict[str, str]:
        self._setup(context, mock_game, actors)
        await CombatOutcomeSystem(mock_game).execute()
        await CombatResultNoticeSystem(mock_game).execute()
        return {
            name: memory.messages[-1].content
            for name, memory in mock_game.world.agent_memories.items()
            if memory.messages
        }

    @pytest.mark.asyncio
    async def test_win_gives_party_victory_and_monster_defeat(
        self, context: ECSContext, mock_game: Any
    ) -> None:
        """队伍全胜：友方读「胜利」，怪物读「失败」，两侧都带 combat_outcome。"""
        ally = _make_actor(context, "英雄", is_ally=True)
        dead_monster = _make_actor(context, "哥布林", is_monster=True, is_dead=True)
        contents = await self._collect(context, mock_game, {ally, dead_monster})

        assert "战斗胜利" in contents["英雄"]
        assert "战斗失败" in contents["哥布林"]

        for name in ("英雄", "哥布林"):
            message = mock_game.world.agent_memories[name].messages[-1]
            assert message.combat_outcome == "测试场景"

    @pytest.mark.asyncio
    async def test_lose_gives_party_defeat_and_monster_victory(
        self, context: ECSContext, mock_game: Any
    ) -> None:
        """队伍全灭：友方读「失败」，怪物读「胜利」。"""
        dead_ally = _make_actor(context, "英雄", is_ally=True, is_dead=True)
        monster = _make_actor(context, "哥布林", is_monster=True)
        contents = await self._collect(context, mock_game, {dead_ally, monster})

        assert "战斗失败" in contents["英雄"]
        assert "战斗胜利" in contents["哥布林"]
