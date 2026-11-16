"""全局唯一 pipeline 的跨阶段守卫测试。"""

from typing import Any

from ai_dbg.game.assembly import create_dbg_game
from ai_dbg.game.entities import create_entity
from ai_dbg.game.lifecycle import initialize_game
from ai_dbg.models import (
    ActorComponent,
    Blueprint,
    CharacterStats,
    CharacterStatsComponent,
    DrawPileComponent,
    EnvironmentComponent,
    PartyMemberComponent,
    PlayerComponent,
    WorldState,
)
from dungeon_support import install_opening_room, make_dungeon_entity


def _make_opening_game() -> Any:
    stage_name = "场景.开场"
    blueprint = Blueprint(
        name="test",
        player_actor="角色.玩家",
        campaign_setting="",
        system_rules="",
        stages=[],
        world_entities=[],
    )
    world = WorldState(
        entity_counter=0,
        entities={},
        agent_memories={},
        blueprint=blueprint,
    )
    game = create_dbg_game(
        name="test",
        player_name="player",
        player_actor="角色.玩家",
        world=world,
    )

    make_dungeon_entity(game, name="副本.测试", profile="")
    stage_entity = install_opening_room(game, room_name=stage_name)
    stage_entity.add(EnvironmentComponent, stage_name, "一片安静的开场空地。")

    player_entity = create_entity(game, "角色.玩家")
    player_entity.add(ActorComponent, "角色.玩家", stage_name)
    player_entity.add(PlayerComponent, "player")
    player_entity.add(
        CharacterStatsComponent,
        "角色.玩家",
        CharacterStats(hp=10, max_hp=10),
    )
    player_entity.add(PartyMemberComponent, "角色.玩家")
    return game


async def test_global_pipeline_is_safe_in_opening_room() -> None:
    """开场房间执行全局 pipeline 时，战斗系统应自行跳过而不是断言失败。"""
    game = _make_opening_game()
    await initialize_game(game)

    await game.pipeline.process(None)

    # 开场初始化应正常写入角色记忆，且没有战斗临时组件被创建。
    player_entity = game.ecs.get_entity_by_name("角色.玩家")
    assert player_entity is not None
    assert game.world.agent_memories["角色.玩家"].messages
    assert not player_entity.has(DrawPileComponent)
