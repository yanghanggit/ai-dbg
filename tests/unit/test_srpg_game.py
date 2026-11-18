from typing import Any, List, Optional

import pytest

from ai_srpg.entitas.entity import Entity
from ai_srpg.game.assembly import create_srpg_game
from ai_srpg.game.context import SRPGGame
from ai_srpg.game.dungeon import (
    current_dungeon_name,
    current_room_index,
    is_player_in_dungeon_stage,
    is_player_in_lobby_stage,
)
from ai_srpg.game.entities import (
    create_entity,
)
from ai_srpg.models import (
    Actor,
    ActorComponent,
    ActorType,
    AppearanceComponent,
    Blueprint,
    CharacterStats,
    CharacterStatsComponent,
    DungeonComponent,
    LobbyComponent,
    NPCComponent,
    PlayerComponent,
    Stage,
    StageComponent,
    StageType,
    WorldState,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_game(
    player_name: str = "p1",
    actor_name: str = "hero",
    blueprint: Optional[Blueprint] = None,
) -> SRPGGame:
    """创建带有空世界的 SRPGGame 实例（不调用 build_from_blueprint）。"""
    if blueprint is None:
        blueprint = Blueprint(
            name="test",
            player_actor=actor_name,
            campaign_setting="",
            system_rules="",
            stages=[],
            world_entities=[],
        )
    world = WorldState(
        entity_counter=0,
        entities={},
        agent_memories={},
        blueprint=blueprint,
    )
    return create_srpg_game(
        name="test",
        player_name=player_name,
        player_actor=actor_name,
        world=world,
    )


def _make_lobby_stage_entity(game: Any, name: str) -> Entity:
    entity: Entity = create_entity(game, name)
    entity.add(StageComponent, name)
    entity.add(LobbyComponent, name)
    return entity


def _make_dungeon_stage_entity(game: Any, name: str) -> Entity:
    entity: Entity = create_entity(game, name)
    entity.add(StageComponent, name)
    entity.add(DungeonComponent, name)
    return entity


def _make_player_actor_entity(
    game: Any, actor_name: str, player_name: str, stage_name: str
) -> Entity:
    entity: Entity = create_entity(game, actor_name)
    entity.add(ActorComponent, actor_name, stage_name)
    entity.add(PlayerComponent, player_name)
    return entity


def _make_actor_entity(game: Any, actor_name: str, stage_name: str = "") -> Entity:
    entity: Entity = create_entity(game, actor_name)
    entity.add(ActorComponent, actor_name, stage_name)
    entity.add(CharacterStatsComponent, actor_name, CharacterStats(hp=20, max_hp=20))
    entity.add(NPCComponent, actor_name)
    entity.add(AppearanceComponent, actor_name, "human body", "")
    return entity


def _make_actor_model(
    name: str,
    actor_type: ActorType = ActorType.NPC,
    hp: int = 30,
    attack: int = 5,
    defense: int = 3,
) -> Actor:
    return Actor(
        name=name,
        type=actor_type,
        profile="",
        base_body="human body",
        system_message=f"{name} is a character.",
        character_stats=CharacterStats(
            hp=hp, max_hp=hp, attack=attack, defense=defense
        ),
        # keywords=["通用型：无特殊约束，自由生成卡牌。"],
    )


def _make_stage_model(
    name: str,
    stage_type: StageType = StageType.LOBBY,
    actors: Optional[List[Actor]] = None,
) -> Stage:
    return Stage(
        name=name,
        type=stage_type,
        profile="",
        system_message=f"{name} is a stage.",
        actors=actors or [],
    )


# ---------------------------------------------------------------------------
# TestCurrentDungeon
# ---------------------------------------------------------------------------


class TestCurrentDungeon:
    def test_empty_world_has_no_dungeon(self, sample_game: Any) -> None:
        assert current_dungeon_name(sample_game) == ""
        assert current_room_index(sample_game) == -1


# ---------------------------------------------------------------------------
# TestIsPlayerInStage
# ---------------------------------------------------------------------------


class TestIsPlayerInStage:
    def test_player_in_lobby_stage_returns_true(self) -> None:
        game = _make_game()
        lobby = _make_lobby_stage_entity(game, "lobby_stage")
        _make_player_actor_entity(game, "hero", "p1", lobby.name)
        assert is_player_in_lobby_stage(game) is True

    def test_player_in_dungeon_stage_returns_false_for_lobby(self) -> None:
        game = _make_game()
        lobby = _make_lobby_stage_entity(game, "lobby_stage")
        _make_player_actor_entity(game, "hero", "p1", lobby.name)
        assert is_player_in_dungeon_stage(game) is False

    def test_player_in_dungeon_stage_returns_true(self) -> None:
        game = _make_game()
        dungeon = _make_dungeon_stage_entity(game, "cave")
        _make_player_actor_entity(game, "hero", "p1", dungeon.name)
        assert is_player_in_dungeon_stage(game) is True

    def test_player_in_lobby_stage_returns_false_for_dungeon(self) -> None:
        game = _make_game()
        dungeon = _make_dungeon_stage_entity(game, "cave")
        _make_player_actor_entity(game, "hero", "p1", dungeon.name)
        assert is_player_in_lobby_stage(game) is False

    def test_no_player_entity_raises(self) -> None:
        game = _make_game()
        with pytest.raises(AssertionError):
            _ = is_player_in_lobby_stage(game)


# ---------------------------------------------------------------------------
# TestBuildFromBlueprint
# ---------------------------------------------------------------------------


class TestBuildFromBlueprint:
    def _make_full_blueprint(self) -> Blueprint:
        ally = _make_actor_model("hero", ActorType.NPC)
        lobby = _make_stage_model("lobby_stage", StageType.LOBBY, actors=[ally])
        return Blueprint(
            name="full_test",
            player_actor="hero",
            campaign_setting="",
            system_rules="",
            stages=[lobby],
            world_entities=[],
        )

    def _make_game_for_build(self) -> SRPGGame:
        bp = self._make_full_blueprint()
        world = WorldState(
            entity_counter=0,
            entities={},
            agent_memories={},
            blueprint=bp,
        )
        return create_srpg_game(
            name="full_test",
            player_name="p1",
            player_actor="hero",
            world=world,
        )

    # def test_actor_entity_created(self) -> None:
    #     game = self._make_game_for_build()
    #     build_from_blueprint(game)
    #     assert get_actor_entity(game, "hero") is not None

    # def test_stage_entity_created(self) -> None:
    #     game = self._make_game_for_build()
    #     build_from_blueprint(game)
    #     assert get_stage_entity(game, "lobby_stage") is not None

    # def test_player_component_assigned(self) -> None:
    #     game = self._make_game_for_build()
    #     build_from_blueprint(game)
    #     hero = get_actor_entity(game, "hero")
    #     assert hero is not None
    #     assert hero.has(PlayerComponent)

    # def test_build_with_existing_entities_raises(self) -> None:
    #     game = self._make_game_for_build()
    #     build_from_blueprint(game)
    #     # entities_serialization is now populated; second call must assert-fail
    #     with pytest.raises(AssertionError):
    #         build_from_blueprint(game)
