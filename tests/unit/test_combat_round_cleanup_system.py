# """CombatRoundCleanupSystem 单元测试。"""

# from unittest.mock import MagicMock

# import pytest

# from ai_dbg.entitas.context import Context
# from ai_dbg.game.context import DBGGame
# from ai_dbg.systems.combat_round_cleanup_system import CombatRoundCleanupSystem


# # ---------------------------------------------------------------------------
# # Helpers
# # ---------------------------------------------------------------------------


# def _make_game(ctx: Context) -> Any:
#     game = MagicMock()
#     game.get_group.side_effect = ctx.get_group
#     return game


# # ---------------------------------------------------------------------------
# # Fixtures
# # ---------------------------------------------------------------------------


# @pytest.fixture()
# def ctx() -> Context:
#     return Context()


# @pytest.fixture()
# def game(ctx: Context) -> Any:
#     return _make_game(ctx)


# @pytest.fixture()
# def system(game: Any) -> CombatRoundCleanupSystem:
#     return CombatRoundCleanupSystem(game)


# # ---------------------------------------------------------------------------
# # execute() 编排逻辑
# # ---------------------------------------------------------------------------


# @pytest.mark.asyncio
# async def test_execute_skips_when_not_ongoing(
#     game: Any, system: CombatRoundCleanupSystem
# ) -> None:
#     cast(Any, current_dungeon_combat_room(mock_game)).combat.is_ongoing = False
#     await system.execute()
#     #game.clear_round_state.assert_not_called()


# @pytest.mark.asyncio
# async def test_execute_skips_when_no_rounds(
#     game: Any, system: CombatRoundCleanupSystem
# ) -> None:
#     cast(Any, current_dungeon_combat_room(mock_game)).combat.is_ongoing = True
#     cast(Any, current_dungeon_combat_room(mock_game)).combat.rounds = []
#     await system.execute()
#     game.clear_round_state.assert_not_called()


# @pytest.mark.asyncio
# async def test_execute_skips_when_round_not_completed(
#     game: Any, system: CombatRoundCleanupSystem
# ) -> None:
#     cast(Any, current_dungeon_combat_room(mock_game)).combat.is_ongoing = True
#     cast(Any, current_dungeon_combat_room(mock_game)).combat.rounds = [MagicMock()]
#     current_dungeon_combat_room(mock_game).combat.latest_round.is_completed = False
#     await system.execute()
#     game.clear_round_state.assert_not_called()


# @pytest.mark.asyncio
# async def test_execute_clears_state_when_completed(
#     game: Any, system: CombatRoundCleanupSystem
# ) -> None:
#     cast(Any, current_dungeon_combat_room(mock_game)).combat.is_ongoing = True
#     cast(Any, current_dungeon_combat_room(mock_game)).combat.rounds = [MagicMock()]
#     current_dungeon_combat_room(mock_game).combat.latest_round.is_completed = True
#     await system.execute()
#     game.clear_round_state.assert_called_once()
