"""服务器世界状态观测。

把跨越各处的「取数 + 判读」逻辑收拢成**一次**结构化快照，
供 AI 代理（``ai_dbg/cli/dbg_agent_api.py``）调用一次 ``status`` 即可掌握当前局面。

设计要点：
- 只读、无副作用；服务端内存才是唯一真相，本模块不缓存任何状态。
- 输出为纯 JSON 可序列化的 dict，字段尽量对齐 ``ai_dbg.models``。
- 玩家角色名（player_actor）可通过 PlayerComponent 反查，因此调用方无需预先登录态。
"""

from typing import Any, Dict, List, NotRequired, Optional, TypedDict

from ..entitas import ComponentData, EntityData
from ..models import (
    AppearanceComponent,
    CharacterStatsComponent,
    CombatView,
    DeathComponent,
    EnvironmentComponent,
    EquippedGearComponent,
    HandComponent,
    InventoryComponent,
    MonsterComponent,
    NPCComponent,
    PlayerComponent,
    compute_effective_stats,
    compute_hand_block,
)
from .server_client import (
    fetch_dungeon_state,
    fetch_entities_details,
    fetch_entities_group,
    fetch_session_messages,
    fetch_stages_state,
)


########################################################################################################################
def component_data(
    components: EntityData, component_name: str
) -> Optional[ComponentData]:
    """在实体的组件 dict 中按组件类名取原始 dict。"""
    data = components.get(component_name)
    return dict(data) if data is not None else None


########################################################################################################################
def find_stage_of_actor(
    actors_by_stage: Dict[str, List[str]], actor_name: str
) -> Optional[str]:
    """在场景映射中查找某角色所在的场景名。"""
    for stage_name, names in actors_by_stage.items():
        if actor_name in names:
            return stage_name
    return None


########################################################################################################################
def role_of(components: EntityData) -> str:
    """依据阵营标记组件返回 "player" / "npc" / "monster" / "unknown"。"""
    if component_data(components, PlayerComponent.__name__) is not None:
        return "player"
    if component_data(components, NPCComponent.__name__) is not None:
        return "npc"
    if component_data(components, MonsterComponent.__name__) is not None:
        return "monster"
    return "unknown"


########################################################################################################################
async def resolve_player_actor(
    user_name: str, game_name: str, actor: Optional[str] = None
) -> str:
    """解析玩家角色名。显式传入时直接使用，否则按 PlayerComponent 反查。"""
    if actor:
        return actor
    resp = await fetch_entities_group(
        user_name,
        game_name,
        all_of=[PlayerComponent.__name__],
        any_of=[],
        none_of=[],
    )
    if not resp.entities:
        raise RuntimeError(
            "未找到玩家实体（PlayerComponent）；请确认已 new-game，或用 --actor 显式指定"
        )
    return next(iter(resp.entities))


########################################################################################################################
class EntitySummary(TypedDict):
    """`_entity_summary` 的结构化输出。

    `name` / `role` / `dead` / `block` / `hand` 所有实体都有；
    `hp` / `max_hp` / `attack` / `defense` / `speed` 仅在 `CharacterStatsComponent` 存在时出现，
    `energy` 仅在战斗中有当前行动槽时出现，`appearance` 仅在 `AppearanceComponent` 存在时出现。
    """

    name: str
    role: str
    dead: bool
    block: int
    hand: List[Dict[str, Any]]
    hp: NotRequired[int]
    max_hp: NotRequired[int]
    attack: NotRequired[int]
    defense: NotRequired[int]
    speed: NotRequired[int]
    energy: NotRequired[int]
    appearance: NotRequired[str]


########################################################################################################################
def _entity_summary(name: str, components: EntityData) -> EntitySummary:
    """把单个实体压缩成代理决策所需的摘要（角色/生死/属性/能量/格挡/手牌）。"""

    hand_data = component_data(components, HandComponent.__name__)
    hand = HandComponent(**hand_data) if hand_data is not None else None

    summary: EntitySummary = {
        "name": name,
        "role": role_of(components),
        "dead": component_data(components, DeathComponent.__name__) is not None,
        "block": compute_hand_block(hand),
        "hand": [card.model_dump(mode="json") for card in hand.cards] if hand else [],
    }

    stats_data = component_data(components, CharacterStatsComponent.__name__)
    if stats_data is not None:
        gear_data = component_data(components, EquippedGearComponent.__name__)
        equipped_gear = (
            EquippedGearComponent(**gear_data) if gear_data is not None else None
        )
        stats = compute_effective_stats(
            CharacterStatsComponent(**stats_data).stats, equipped_gear
        )
        summary["hp"] = stats.hp
        summary["max_hp"] = stats.max_hp
        summary["attack"] = stats.attack
        summary["defense"] = stats.defense
        summary["speed"] = stats.speed

    appearance = component_data(components, AppearanceComponent.__name__)
    if appearance is not None:
        summary["appearance"] = AppearanceComponent(**appearance).appearance

    return summary


########################################################################################################################
def _round_summary(combat: CombatView) -> Optional[Dict[str, Any]]:
    """最近一回合的回合内状态。"""
    latest = combat.latest_round
    if latest is None:
        return None
    return {
        "draw_completed": latest.draw_completed,
        "is_completed": latest.is_completed,
        "current_actor": latest.current_actor,
        "action_order": list(latest.action_order),
        "completed_actors": list(latest.completed_actors),
        "turns": [turn.model_dump() for turn in latest.turns],
    }


########################################################################################################################
def _player_extras(components: EntityData) -> Dict[str, Any]:
    """从玩家实体取随身背包。"""
    inventory_data = component_data(components, InventoryComponent.__name__)
    inventory = (
        [
            item.model_dump(mode="json")
            for item in InventoryComponent(**inventory_data).items
        ]
        if inventory_data
        else []
    )
    return {"inventory": inventory}


########################################################################################################################
def _combat_info(combat: CombatView) -> Dict[str, Any]:
    return {
        "name": combat.name,
        "state": combat.state.name,
        "result": combat.result.name,
        "retreated": combat.retreated,
        "round_count": len(combat.rounds),
        "round": _round_summary(combat),
    }


########################################################################################################################
async def build_status(
    user_name: str,
    game_name: str,
    actor: Optional[str] = None,
    messages_since: int = 0,
) -> Dict[str, Any]:
    """构建当前世界状态快照。

    Args:
        user_name: 用户名
        game_name: 游戏名
        actor: 玩家角色名；None 时按 PlayerComponent 反查
        messages_since: 拉取会话消息的起始 sequence_id（0 表示全量）
    """
    player_actor = await resolve_player_actor(user_name, game_name, actor)

    stages_resp = await fetch_stages_state(user_name, game_name)
    stage_name = find_stage_of_actor(stages_resp.actors_by_stage, player_actor)
    actor_names = (
        list(stages_resp.actors_by_stage.get(stage_name, [])) if stage_name else []
    )
    entity_names = ([stage_name] if stage_name else []) + actor_names

    details_resp = await fetch_entities_details(user_name, game_name, entity_names)
    entities_by_name = details_resp.entities

    # 场景描述
    stage_block: Dict[str, Any] = {"name": stage_name, "actors": actor_names}
    if stage_name is not None:
        stage_entity = entities_by_name.get(stage_name)
        narrative = None
        if stage_entity is not None:
            env_data = component_data(stage_entity, EnvironmentComponent.__name__)
            if env_data is not None:
                narrative = EnvironmentComponent(**env_data).narrative
        stage_block["narrative"] = narrative

    status: Dict[str, Any] = {
        "user_name": user_name,
        "game_name": game_name,
        "player_actor": player_actor,
        "stage": stage_block,
        "entities": [
            _entity_summary(name, components)
            for name, components in entities_by_name.items()
        ],
    }

    # 副本 / 战斗
    dungeon_resp = await fetch_dungeon_state(user_name, game_name)
    dungeon = dungeon_resp.dungeon
    room = dungeon.current_room
    mode = "dungeon" if room is not None else "lobby"
    status["mode"] = mode
    status["dungeon"] = {
        "name": dungeon.name,
        "current_room_index": dungeon.current_room_index,
        "room_count": len(dungeon.rooms),
        "room_type": room.type if room is not None else None,
    }

    if room is not None and room.combat is not None:
        status["combat"] = _combat_info(room.combat)
        latest_round = room.combat.latest_round
        if latest_round is not None:
            energy_by_actor = {
                turn.actor_name: turn.energy for turn in latest_round.turns
            }
            for summary in status["entities"]:
                energy = energy_by_actor.get(summary["name"])
                if energy is not None:
                    summary["energy"] = energy
    # 玩家随身背包
    player_entity = entities_by_name.get(player_actor)
    if player_entity is not None:
        status["player"] = _player_extras(player_entity)

    # 会话消息
    messages_resp = await fetch_session_messages(user_name, messages_since)
    status["session_messages"] = [
        message.model_dump(mode="json") for message in messages_resp.session_messages
    ]

    return status
