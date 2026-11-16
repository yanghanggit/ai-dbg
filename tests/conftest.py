"""Test configuration and fixtures."""

import pytest

from ai_dbg.game.assembly import create_dbg_game
from ai_dbg.game.context import DBGGame
from ai_dbg.game.events import RecordingEventSink
from ai_dbg.models import (
    Actor,
    ActorType,
    Blueprint,
    CharacterStats,
    WorldState,
)


@pytest.fixture
def sample_game() -> DBGGame:
    """Create a sample game for testing."""
    # 创建基本的依赖
    blueprint = Blueprint(
        name="test_blueprint",
        player_actor="test_player_actor",
        campaign_setting="test_setting",
        system_rules="",
        stages=[],
        world_entities=[],
    )
    world = WorldState(
        entity_counter=1000,
        entities={},
        agent_memories={},
        blueprint=blueprint,
    )
    return create_dbg_game(
        name="test_blueprint",
        player_name="test_player",
        player_actor="test_actor",
        world=world,
        events=RecordingEventSink(),
    )


@pytest.fixture
def sample_actor() -> Actor:
    """Create a sample actor for testing."""
    return Actor(
        name="test_actor",
        type=ActorType.NPC,
        profile="test profile",
        base_body="",
        system_message="test system message",
        character_stats=CharacterStats(max_hp=50, attack=10, defense=5),
    )
