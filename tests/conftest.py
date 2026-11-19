"""Test configuration and fixtures."""

import pytest

from ai_srpg.game.assembly import create_srpg_game
from ai_srpg.game.context import SRPGGame
from ai_srpg.game.events.sink import RecordingEventSink
from ai_srpg.models import (
    ActorBlueprint,
    ActorComponent,
)


@pytest.fixture
def sample_game() -> SRPGGame:
    """Create a sample game for testing."""
    return create_srpg_game(name="test_blueprint", events=RecordingEventSink())


@pytest.fixture
def sample_actor() -> ActorBlueprint:
    """Create a sample actor blueprint for testing."""
    return ActorBlueprint(
        name="test_actor",
        system_message="test system message",
        components={ActorComponent.__name__: {"current_stage": "test_stage"}},
        assets={"portrait": ".assets/image/test.meta"},
    )
