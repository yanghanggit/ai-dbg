"""两层世界的最小夹具：一张 5x5 战役地图，一个据点（含一个内部区域），一名哨兵。

据点 舞台.营地 在 (2,2)，它有子区域 舞台.火房；哨塔 在相邻的 (3,2)。
角色.甲、角色.乙 在营地里，角色.丙 在哨塔里，角色.丁 站在地图 (1,1)。
"""

from typing import Dict, List

from ai_srpg.entitas import Entity
from ai_srpg.game.assembly import create_srpg_game
from ai_srpg.game.context import SRPGGame
from ai_srpg.game.entities import build_from_blueprint
from ai_srpg.game.memory import get_agent_memory
from ai_srpg.models import (
    ActorBlueprint,
    ActorComponent,
    AppearanceComponent,
    Blueprint,
    ChatMessage,
    EnvironmentComponent,
    GlobalStageComponent,
    Position,
    PositionComponent,
    StageBlueprint,
    StageComponent,
)

BATTLEFIELD = "舞台.战场"
CAMP = "舞台.营地"
FIRE_ROOM = "舞台.火房"
TOWER = "舞台.哨塔"

HERE = "角色.甲"
OTHER = "角色.乙"
SENTRY = "角色.丙"
WANDERER = "角色.丁"

CAMP_ENVIRONMENT = "碎石浅坑，压实的灰土，风被石头切开"


def build_world(name: str = "TwoLevelWorld") -> SRPGGame:
    game = create_srpg_game(name=name)
    build_from_blueprint(
        game,
        Blueprint(
            name=name,
            campaign_setting="设定",
            global_rules="规则",
            stage_tree=StageBlueprint(
                name=BATTLEFIELD,
                system_message=f"{BATTLEFIELD} 的设定",
                components={
                    StageComponent.__name__: {},
                    GlobalStageComponent.__name__: {"width": 5, "height": 5},
                },
                children=[
                    StageBlueprint(
                        name=CAMP,
                        system_message=f"{CAMP} 的设定",
                        components={
                            StageComponent.__name__: {},
                            EnvironmentComponent.__name__: {
                                "base_environment": CAMP_ENVIRONMENT
                            },
                        },
                        position=Position(x=2, y=2),
                        children=[
                            StageBlueprint(
                                name=FIRE_ROOM,
                                system_message=f"{FIRE_ROOM} 的设定",
                                components={StageComponent.__name__: {}},
                            )
                        ],
                    ),
                    StageBlueprint(
                        name=TOWER,
                        system_message=f"{TOWER} 的设定",
                        components={StageComponent.__name__: {}},
                        position=Position(x=3, y=2),
                    ),
                ],
            ),
            actors=[
                _actor(HERE, CAMP),
                _actor(OTHER, CAMP),
                _actor(SENTRY, TOWER),
                _actor(WANDERER, BATTLEFIELD, Position(x=1, y=1)),
            ],
            worlds=[],
        ),
    )
    return game


def entity(game: SRPGGame, name: str) -> Entity:
    found = game.get_entity_by_name(name)
    assert found is not None
    return found


def messages(game: SRPGGame, name: str) -> List[ChatMessage]:
    """除首条 system 设定以外的记忆。"""
    return list(get_agent_memory(game, entity(game, name)).messages[1:])


def heard(game: SRPGGame, name: str) -> List[str]:
    """该实体收到的广播文本。"""
    return [
        message.content
        for message in messages(game, name)
        if getattr(message, "agent_event", None) is not None
    ]


def said(game: SRPGGame, name: str) -> List[str]:
    """该实体记忆里的全部文本（含自述）。"""
    return [message.content for message in messages(game, name)]


def _actor(name: str, stage: str, cell: Position | None = None) -> ActorBlueprint:
    components: Dict[str, Dict[str, object]] = {
        ActorComponent.__name__: {"current_stage": stage},
        AppearanceComponent.__name__: {"base_body": f"{name}的样子"},
    }
    if cell is not None:
        components[PositionComponent.__name__] = {"x": cell.x, "y": cell.y}
    return ActorBlueprint(
        name=name, system_message=f"{name} 的设定", components=components
    )


__all__ = [
    "BATTLEFIELD",
    "CAMP",
    "CAMP_ENVIRONMENT",
    "FIRE_ROOM",
    "HERE",
    "OTHER",
    "SENTRY",
    "TOWER",
    "WANDERER",
    "build_world",
    "entity",
    "heard",
    "messages",
    "said",
]
