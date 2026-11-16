"""场景环境、外观与场景转换。"""

from .appearance import get_actor_appearances_in_stage
from .environment import (
    MISSING_ENVIRONMENT_NARRATIVE,
    get_stage_environment,
)
from .transition import stage_transition

__all__ = [
    "MISSING_ENVIRONMENT_NARRATIVE",
    "get_actor_appearances_in_stage",
    "get_stage_environment",
    "stage_transition",
]
