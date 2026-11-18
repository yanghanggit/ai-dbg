"""供测试复用的通用 ECS 组件（Position/Velocity/Health …）。

这些组件不属于游戏玩法，而是 entitas 单测/集成测试的公共夹具，因此放在测试树
（``tests/ecs_testing.py``）而非发布包 ``ai_srpg.entitas`` 内。所有组件基于 Pydantic
BaseModel。
"""

from ai_srpg.entitas.components import Component


# Basic components for testing
class Position(Component):
    """Position component with x, y coordinates."""

    x: float
    y: float


class Velocity(Component):
    """Velocity component with dx, dy movement."""

    dx: float
    dy: float


class Health(Component):
    """Health component with current and max values."""

    value: int
    max_value: int

    def model_post_init(self, __context: None) -> None:
        """Validate health values after initialization."""
        if self.value < 0:
            raise ValueError("Health value must be non-negative")
        if self.max_value <= 0:
            raise ValueError("Max health must be positive")
        if self.value > self.max_value:
            raise ValueError("Health value cannot exceed max health")


class Name(Component):
    """Name component with string value."""

    value: str


class Age(Component):
    """Age component with integer value."""

    value: int


class Score(Component):
    """Score component with integer value."""

    value: int


class Damage(Component):
    """Damage component with integer value."""

    value: int


class Defense(Component):
    """Defense component with integer value."""

    value: int


# Component without fields for edge case testing
class Marker(Component):
    """Marker component without any fields."""

    pass


# Multi-field component
class Transform(Component):
    """Transform component with position, rotation and scale."""

    x: float
    y: float
    rotation: float
    scale: float


# 不可变组件示例：用于验证冻结语义与 replace 写入
class Counter(Component):
    """Counter component used to verify frozen components require replace."""

    value: int = 0
