from typing import Any

"""dungeon_spoils_actions 单元测试：奖励与非战斗房间语义。"""

from typing import cast
from unittest.mock import MagicMock

import pytest

from ai_dbg.entitas.context import Context
from ai_dbg.entitas.entity import Entity
from ai_dbg.models import (
    ActorComponent,
    DeckComponent,
    DungeonComponent,
    GenerateSpoilsAction,
    LobbyComponent,
    PartyMemberComponent,
    PlayerComponent,
    SpoilsComponent,
    StageComponent,
)
from ai_dbg.services.dungeon_spoils_actions import (
    activate_generate_spoils,
    remove_spoils,
)
from dungeon_support import (
    install_combat,
    install_opening_room,
    make_dungeon_entity,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_party_member(context: Context, name: str) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "")
    entity.add(DeckComponent, name, [])
    entity.add(PartyMemberComponent, name)
    return entity


def _mock_game(
    party: set[Entity], *, in_dungeon: bool = True, in_combat: bool = False
) -> Any:
    member = next(iter(party))
    context = cast(Context, member._context)
    game = MagicMock()
    game.ecs = context
    game.entity_index = {}
    game.world.agent_memories = {}
    game.player_session = MagicMock()
    stage = context.create_entity()
    stage._name = "场景.测试"
    stage.add(StageComponent, stage.name)
    if in_dungeon:
        stage.add(DungeonComponent, stage.name)
    else:
        stage.add(LobbyComponent, stage.name)
    for entity in party:
        entity.replace(ActorComponent, entity.name, stage.name)
    member.add(PlayerComponent, member.name)
    if in_dungeon:
        make_dungeon_entity(game)
        if in_combat:
            install_combat(game, room_name=stage.name)
        else:
            install_opening_room(game, room_name=stage.name)
    return game


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> Context:
    return Context()


# ---------------------------------------------------------------------------
# remove_spoils
# ---------------------------------------------------------------------------


def test_remove_spoils_clears_party(context: Context) -> None:
    member = _make_party_member(context, "英雄")
    member.add(SpoilsComponent, "英雄", [], [])
    game = _mock_game({member})

    ok, _ = remove_spoils(game)

    assert ok is True
    assert not member.has(SpoilsComponent)


def test_remove_spoils_rejects_when_nothing_to_clear(context: Context) -> None:
    member = _make_party_member(context, "英雄")
    game = _mock_game({member})

    ok, _ = remove_spoils(game)

    assert ok is False


def test_remove_spoils_rejects_outside_dungeon(context: Context) -> None:
    member = _make_party_member(context, "英雄")
    member.add(SpoilsComponent, "英雄", [], [])
    game = _mock_game({member}, in_dungeon=False)

    ok, _ = remove_spoils(game)

    assert ok is False
    assert member.has(SpoilsComponent)


# ---------------------------------------------------------------------------
# activate_generate_spoils
# ---------------------------------------------------------------------------


def test_generate_spoils_rejected_in_combat_room(context: Context) -> None:
    member = _make_party_member(context, "英雄")
    game = _mock_game({member}, in_combat=True)

    ok, msg = activate_generate_spoils(game)

    assert ok is False
    assert "战斗房间" in msg


def test_generate_spoils_rejected_when_already_generated(context: Context) -> None:
    member = _make_party_member(context, "英雄")
    member.add(SpoilsComponent, "英雄", [], [])
    game = _mock_game({member})

    ok, _ = activate_generate_spoils(game)

    assert ok is False


def test_generate_spoils_activates_action_in_non_combat_room(context: Context) -> None:
    member = _make_party_member(context, "英雄")
    game = _mock_game({member})

    ok, _ = activate_generate_spoils(game)

    assert ok is True
    assert member.has(GenerateSpoilsAction)


###################################################################################################################################################################
def test_party_has_any_spoils_requires_component() -> None:
    """「生成完了但零产出」可被判定：队内无 SpoilsComponent 即视为未完成。"""
    from ai_dbg.entitas.context import Context
    from ai_dbg.models import (
        ActorComponent,
        Card,
        PartyMemberComponent,
        SpoilsComponent,
    )
    from ai_dbg.services.dungeon_spoils_actions import party_has_any_spoils

    context = Context()
    game = MagicMock()
    game.ecs = context
    game.entity_index = {}

    entity = context.create_entity()
    entity._name = "角色.无名"
    entity.add(ActorComponent, entity.name, "")
    entity.add(PartyMemberComponent, entity.name)

    assert party_has_any_spoils(game) is False

    entity.add(
        SpoilsComponent,
        entity.name,
        [Card(name="候选", description="")],
        [],
    )

    assert party_has_any_spoils(game) is True
