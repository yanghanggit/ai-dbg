"""
Test Pydantic BaseModel component functionality.
This tests the new Pydantic-based component system.
"""

import pytest

from ai_srpg.entitas import Context, Entity, Matcher
from ai_srpg.entitas.components import Component
from ecs_testing import Counter, Health, Marker, Position


def _new_entity() -> Entity:
    """Creates a fresh context-bound entity for a single-component test."""
    return Context().create_entity()


class TestPydanticComponents:
    """Test cases for Pydantic BaseModel components."""

    def test_component_creation_and_validation(self) -> None:
        """Test that Pydantic components are created and validated correctly."""
        entity = _new_entity()

        # Test normal component creation
        entity.add(Position, 10.0, 20.0)
        pos = entity.get(Position)
        assert pos.x == 10.0
        assert pos.y == 20.0
        assert isinstance(pos, Component)

        # Test component with validation
        entity.add(Health, 100, 150)
        health = entity.get(Health)
        assert health.value == 100
        assert health.max_value == 150

    def test_component_validation_errors(self) -> None:
        """Test that Pydantic validation works correctly."""
        entity = _new_entity()

        # Test negative health value
        with pytest.raises(ValueError, match="Health value must be non-negative"):
            entity.add(Health, -10, 100)

        # Test zero max health
        with pytest.raises(ValueError, match="Max health must be positive"):
            entity.add(Health, 50, 0)

        # Test value exceeding max health
        with pytest.raises(ValueError, match="Health value cannot exceed max health"):
            entity.add(Health, 150, 100)

    def test_component_without_fields(self) -> None:
        """Test component without fields (Marker)."""
        entity = _new_entity()

        # Should work with no arguments
        entity.add(Marker)
        assert entity.has(Marker)
        marker = entity.get(Marker)
        assert isinstance(marker, Component)

        # Should fail with arguments
        entity2 = _new_entity()
        with pytest.raises(ValueError, match="expects no arguments"):
            entity2.add(Marker, "extra_arg")

    def test_component_wrong_argument_count(self) -> None:
        """Test error handling for wrong number of arguments."""
        entity = _new_entity()

        # Too few arguments
        with pytest.raises(ValueError, match="expects 2 arguments"):
            entity.add(Position, 10.0)

        # Too many arguments
        with pytest.raises(ValueError, match="expects 2 arguments"):
            entity.add(Position, 10.0, 20.0, 30.0)

    def test_component_serialization(self) -> None:
        """Test that Pydantic components can be serialized."""
        entity = _new_entity()

        entity.add(Position, 10.0, 20.0)
        entity.add(Health, 100, 150)

        pos = entity.get(Position)
        health = entity.get(Health)

        # Test JSON serialization
        pos_json = pos.model_dump_json()
        health_json = health.model_dump_json()

        assert '"x":10.0' in pos_json
        assert '"y":20.0' in pos_json
        assert '"value":100' in health_json
        assert '"max_value":150' in health_json

        # Test deserialization
        pos_dict = pos.model_dump()
        new_pos = Position(**pos_dict)
        assert new_pos.x == pos.x
        assert new_pos.y == pos.y

    def test_component_representation(self) -> None:
        """Test component string representation."""
        entity = _new_entity()

        entity.add(Position, 10.0, 20.0)
        entity.add(Health, 100, 150)

        pos = entity.get(Position)
        health = entity.get(Health)

        pos_str = str(pos)
        health_str = str(health)

        assert "Position" in pos_str
        assert "x=10.0" in pos_str
        assert "y=20.0" in pos_str

        assert "Health" in health_str
        assert "value=100" in health_str
        assert "max_value=150" in health_str

    def test_component_equality(self) -> None:
        """Test component equality comparison."""
        # Two components with same values should be equal
        pos1 = Position(x=10.0, y=20.0)
        pos2 = Position(x=10.0, y=20.0)
        pos3 = Position(x=15.0, y=25.0)

        assert pos1 == pos2
        assert pos1 != pos3

    def test_integration_with_context_and_groups(self) -> None:
        """Test that Pydantic components work correctly with Context and Groups."""
        context = Context()

        # Create entities with Pydantic components
        entity1 = context.create_entity()
        entity1.add(Position, 0.0, 0.0)
        entity1.add(Health, 100, 100)

        entity2 = context.create_entity()
        entity2.add(Position, 10.0, 10.0)

        # Test group functionality
        positioned_group = context.get_group(Matcher(Position))
        living_group = context.get_group(Matcher(Health))
        living_positioned_group = context.get_group(Matcher(Position, Health))

        assert len(positioned_group.entities) == 2
        assert len(living_group.entities) == 1
        assert len(living_positioned_group.entities) == 1

        # Test component access through groups
        for entity in positioned_group.entities:
            pos = entity.get(Position)
            assert isinstance(pos, Position)
            assert hasattr(pos, "x")
            assert hasattr(pos, "y")

    def test_component_model_is_frozen(self) -> None:
        """组件基类默认冻结：字段赋值必须被拒绝。"""
        assert Component.model_config.get("frozen") is True

    def test_component_is_immutable(self) -> None:
        """直接给组件字段赋值会失败，读取仍是原值。"""
        entity = _new_entity()
        entity.add(Counter, 5)
        counter = entity.get(Counter)

        with pytest.raises(ValueError, match="frozen"):
            counter.value = 10

        assert counter.value == 5

    def test_component_update_requires_replace(self) -> None:
        """修改组件必须 replace：旧实例保持不变，新实例生效。"""
        entity = _new_entity()
        entity.add(Counter, 5)
        old = entity.get(Counter)

        entity.replace(Counter, 10)
        new = entity.get(Counter)

        assert old.value == 5
        assert new.value == 10
        assert new is not old

    def test_frozen_component_replace_updates_group(self) -> None:
        """replace 冻结组件后，分组仍包含实体且读到新值。"""
        context = Context()
        entity = context.create_entity()
        entity.add(Counter, 5)
        group = context.get_group(Matcher(Counter))

        entity.replace(Counter, 10)

        assert entity in group.entities
        assert entity.get(Counter).value == 10
