"""Test the fixtures in conftest.py to ensure they work correctly."""

from typing import Any


def test_sample_game_fixture(sample_game: Any) -> None:
    """Test that the sample_game fixture creates a valid game instance."""
    assert sample_game is not None
    assert hasattr(sample_game, "name")
    assert sample_game.name == "test_blueprint"
    assert not hasattr(sample_game, "session")


def test_sample_actor_fixture(sample_actor: Any) -> None:
    """Test that the sample_actor fixture creates a valid actor blueprint."""
    assert sample_actor is not None
    assert sample_actor.name == "test_actor"
    assert sample_actor.system_message == "test system message"
    assert sample_actor.components["ActorComponent"]["current_stage"] == "test_stage"
    assert sample_actor.assets["portrait"] == ".assets/image/test.meta"
