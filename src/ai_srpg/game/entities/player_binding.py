"""玩家与角色的绑定：把某个角色交给某个玩家控制。

``PlayerComponent`` 是这条绑定的唯一事实源：一人一个角色、一个角色一人。
读侧按身份查（见 ``queries.get_player_entity``），写侧只走本模块。
"""

from ...entitas import Entity
from ...models import PlayerComponent
from ..context import SRPGGame
from .queries import get_actor_entity, get_player_entity


############################################################################################################
def bind_player_actor(srpg_game: SRPGGame, user_name: str, actor_name: str) -> Entity:
    """把 ``actor_name`` 交给 ``user_name`` 控制；重复绑同一对是幂等的。

    同一角色已被别人控制、或该玩家已经在控制别的角色时抛 ``ValueError``——
    这两种情况都意味着调用方对局面的判断已过期。
    """
    if not user_name.strip():
        raise ValueError("玩家名不能为空")
    if not actor_name.strip():
        raise ValueError("角色名不能为空")

    actor = get_actor_entity(srpg_game, actor_name)
    if actor is None:
        raise ValueError(f"找不到角色实体: {actor_name}")

    if actor.has(PlayerComponent):
        holder = actor.get(PlayerComponent).user_name
        if holder == user_name:
            return actor
        raise ValueError(f"角色 {actor_name} 已由 {holder} 控制")

    controlling = get_player_entity(srpg_game, user_name)
    if controlling is not None:
        raise ValueError(f"玩家 {user_name} 已控制角色 {controlling.name}")

    actor.replace(PlayerComponent, user_name)
    return actor


############################################################################################################
__all__ = ["bind_player_actor"]
