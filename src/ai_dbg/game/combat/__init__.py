"""战斗规则：属性、目标解析与回合状态。"""

from .rounds import (
    assert_no_residual_combat_state,
    clear_round_state,
    get_current_turn_actor,
)
from .stats import (
    compute_character_hand_block,
    compute_character_stats,
    consume_energy,
    get_energy,
    mark_dead,
    set_character_hp,
)
from .targeting import (
    get_alive_actors_in_stage,
    get_alive_monsters_in_stage,
    get_alive_party_members_in_stage,
    resolve_targets,
)

__all__ = [
    "assert_no_residual_combat_state",
    "clear_round_state",
    "compute_character_hand_block",
    "compute_character_stats",
    "consume_energy",
    "get_alive_actors_in_stage",
    "get_alive_monsters_in_stage",
    "get_alive_party_members_in_stage",
    "get_current_turn_actor",
    "get_energy",
    "mark_dead",
    "resolve_targets",
    "set_character_hp",
]
