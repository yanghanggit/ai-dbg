"""Test configuration and fixtures."""

import pytest

from ai_srpg.game.assembly import create_srpg_game
from ai_srpg.game.context import SRPGGame
from ai_srpg.game.events.sink import RecordingEventSink
from ai_srpg.models import (
    Actor,
    ActorType,
    Blueprint,
    WorldState,
)


@pytest.fixture
def sample_game() -> SRPGGame:
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
    return create_srpg_game(
        name="test_blueprint",
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
    )
