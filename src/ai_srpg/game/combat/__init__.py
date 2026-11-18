"""战斗规则基础设施：角色属性、存活查询与目标解析。"""

from .stats import (
    compute_character_stats,
    consume_turn_energy,
    get_turn_energy,
    mark_dead,
    set_character_hp,
)
from .targeting import (
    get_alive_actors_in_stage,
    get_alive_monsters_in_stage,
    get_alive_players_in_stage,
    resolve_targets,
)

__all__ = [
    "compute_character_stats",
    "consume_turn_energy",
    "get_alive_actors_in_stage",
    "get_alive_monsters_in_stage",
    "get_alive_players_in_stage",
    "get_turn_energy",
    "mark_dead",
    "resolve_targets",
    "set_character_hp",
]
