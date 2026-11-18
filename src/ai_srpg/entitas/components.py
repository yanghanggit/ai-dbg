"""
Base classes and utilities for creating components in the ECS system.
Provides both namedtuple compatibility and Pydantic BaseModel support.
"""

from pydantic import BaseModel, ConfigDict


class Component(BaseModel):
    """Base class for all Pydantic-based components.

    Components are immutable value objects: field assignment raises, and any
    change must go through ``Entity.add`` / ``Entity.replace`` / ``Entity.remove``
    so that observers and groups see it.

    This provides:
    - Automatic validation of field types
    - JSON serialization/deserialization
    - Documentation generation
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,  # Allows custom types if needed
        str_strip_whitespace=True,  # Auto-strip strings
        frozen=True,  # 组件是只读值对象；修改必须走 Entity.replace
    )

    def __repr__(self) -> str:
        """Custom representation that matches namedtuple style."""
        field_values = []
        for field_name, field_value in self.__dict__.items():
            if isinstance(field_value, str):
                field_values.append(f"{field_name}='{field_value}'")
            else:
                field_values.append(f"{field_name}={field_value}")
        return f"{self.__class__.__name__}({', '.join(field_values)})"

    def __str__(self) -> str:
        """String representation - same as __repr__ for consistency."""
        return self.__repr__()
