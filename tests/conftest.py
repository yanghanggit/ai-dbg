"""Test configuration and fixtures."""

import pytest

from ai_srpg.game.assembly import create_srpg_game
from ai_srpg.game.context import SRPGGame
from ai_srpg.game.events.sink import RecordingEventSink
from ai_srpg.models import Actor, ActorType


@pytest.fixture
def sample_game() -> SRPGGame:
    """Create a sample game for testing."""
    return create_srpg_game(name="test_blueprint", events=RecordingEventSink())


@pytest.fixture
def sample_actor() -> Actor:
    """Create a sample actor for testing."""
    return Actor(
        name="test_actor",
        type=ActorType.NONE,
        profile="test profile",
        base_body="",
        system_message="test system message",
    )
