"""蓝图装配的显式约束：类别标记、舞台树、网格坐标、名字唯一。

蓝图只给名字、``memories[0]`` 与组件数据；类别不靠枚举，而靠装配期要求实体带对了
标记组件——漏写就是内容写错，必须当场失败。
"""

from typing import Any, Dict, List, Optional

import pytest

from ai_srpg.game.assembly import create_srpg_game
from ai_srpg.game.context import SRPGGame
from ai_srpg.game.entities import (
    build_from_blueprint,
    get_actor_entity,
    get_stage_entity,
)
from ai_srpg.models import (
    ActorBlueprint,
    ActorComponent,
    AppearanceComponent,
    Blueprint,
    GlobalStageComponent,
    Position,
    PositionComponent,
    StageBlueprint,
    StageComponent,
    WorldBlueprint,
)

GRID = {"width": 5, "height": 5}


###############################################################################
def _world() -> WorldBlueprint:
    return WorldBlueprint(
        name="世界.甲",
        system_message="世界.甲 的设定",
        components={"WorldComponent": {}},
    )


def _battlefield(
    *,
    components: Optional[Dict[str, Dict[str, Any]]] = None,
    children: Optional[List[StageBlueprint]] = None,
) -> StageBlueprint:
    return StageBlueprint(
        name="舞台.战场",
        system_message="舞台.战场 的设定",
        components=(
            {"StageComponent": {}, "GlobalStageComponent": dict(GRID)}
            if components is None
            else components
        ),
        children=children or [],
    )


def _camp(
    position: Optional[Position] = None, *, name: str = "舞台.营地"
) -> StageBlueprint:
    return StageBlueprint(
        name=name,
        system_message=f"{name} 的设定",
        components={"StageComponent": {}},
        position=position,
    )


def _blueprint(
    *,
    root: Optional[StageBlueprint] = None,
    actor_components: Optional[Dict[str, Dict[str, Any]]] = None,
    actor_stage: str = "舞台.营地",
    actors: Optional[List[ActorBlueprint]] = None,
    worlds: Optional[List[WorldBlueprint]] = None,
) -> Blueprint:
    return Blueprint(
        name="BuildTest",
        campaign_setting="设定",
        global_rules="规则",
        root_stage=(
            root
            if root is not None
            else _battlefield(children=[_camp(Position(x=2, y=2))])
        ),
        actors=(
            actors
            if actors is not None
            else [
                ActorBlueprint(
                    name="角色.甲",
                    system_message="角色.甲 的设定",
                    components=(
                        {"ActorComponent": {"current_stage": actor_stage}}
                        if actor_components is None
                        else actor_components
                    ),
                )
            ]
        ),
        world_entities=[_world()] if worlds is None else worlds,
    )


###############################################################################
def test_components_land_on_the_entity_verbatim() -> None:
    """组件数据原样进 ECS，装配期不猜任何字段。"""
    game = create_srpg_game(name="BuildTest")
    blueprint = _blueprint(
        actor_components={
            "ActorComponent": {"current_stage": "舞台.营地"},
            "AppearanceComponent": {"base_body": "瘦削"},
        }
    )

    build_from_blueprint(game, blueprint)

    actor = get_actor_entity(game, "角色.甲")
    assert actor is not None
    assert actor.get(AppearanceComponent).base_body == "瘦削"


###############################################################################
def test_appearance_defaults_to_base_body() -> None:
    """没给外观时，外观与基础体型相同——内容侧不必写两遍同一段文字。"""
    game = create_srpg_game(name="BuildTest")
    build_from_blueprint(
        game,
        _blueprint(
            actor_components={
                "ActorComponent": {"current_stage": "舞台.营地"},
                "AppearanceComponent": {"base_body": "瘦削"},
            }
        ),
    )

    actor = get_actor_entity(game, "角色.甲")
    assert actor is not None
    appearance = actor.get(AppearanceComponent)
    assert appearance.appearance == appearance.base_body == "瘦削"


###############################################################################
def test_stage_tree_sets_parent_and_position() -> None:
    """父子关系由嵌套决定，坐标由蓝图落成 ``PositionComponent``。"""
    game = create_srpg_game(name="BuildTest")
    build_from_blueprint(game, _blueprint())

    battlefield = get_stage_entity(game, "舞台.战场")
    camp = get_stage_entity(game, "舞台.营地")
    assert battlefield is not None and camp is not None
    assert battlefield.get(StageComponent).parent_stage is None
    assert battlefield.get(GlobalStageComponent).width == 5
    assert camp.get(StageComponent).parent_stage == "舞台.战场"
    position = camp.get(PositionComponent)
    assert (position.x, position.y) == (2, 2)


###############################################################################
def test_missing_actor_marker_is_rejected() -> None:
    """没挂 ``ActorComponent`` 的角色只是一个普通实体，必须当场报错。"""
    game = create_srpg_game(name="BuildTest")

    with pytest.raises(AssertionError, match="缺少标记组件 ActorComponent"):
        build_from_blueprint(
            game,
            _blueprint(actor_components={"AppearanceComponent": {"base_body": "瘦削"}}),
        )


###############################################################################
def test_missing_stage_marker_is_rejected() -> None:
    """没挂 ``StageComponent`` 的舞台不会被下游认出来，同样当场报错。"""
    game = create_srpg_game(name="BuildTest")

    with pytest.raises(AssertionError, match="缺少标记组件 StageComponent"):
        build_from_blueprint(
            game,
            _blueprint(
                root=_battlefield(components={"GlobalStageComponent": dict(GRID)})
            ),
        )


###############################################################################
def test_root_stage_must_be_global() -> None:
    """舞台树的根必须是全局舞台——否则整棵树没有坐标系。"""
    game = create_srpg_game(name="BuildTest")
    root = StageBlueprint(
        name="舞台.战场",
        system_message="舞台.战场 的设定",
        components={"StageComponent": {}},
    )

    with pytest.raises(AssertionError, match="根舞台必须是全局舞台"):
        build_from_blueprint(game, _blueprint(root=root))


###############################################################################
def test_only_the_root_stage_may_be_global() -> None:
    """全局舞台只能有一个，且只能是根。"""
    game = create_srpg_game(name="BuildTest")
    child = StageBlueprint(
        name="舞台.营地",
        system_message="舞台.营地 的设定",
        components={"StageComponent": {}, "GlobalStageComponent": dict(GRID)},
        position=Position(x=0, y=0),
    )

    with pytest.raises(AssertionError, match="只有根舞台可以是全局舞台"):
        build_from_blueprint(
            game,
            _blueprint(root=_battlefield(children=[child])),
        )


###############################################################################
def test_child_stage_needs_a_position() -> None:
    """父舞台有网格时，子舞台必须说明自己在哪一格。"""
    game = create_srpg_game(name="BuildTest")

    with pytest.raises(AssertionError, match="没有位置"):
        build_from_blueprint(
            game,
            _blueprint(root=_battlefield(children=[_camp()])),
        )


###############################################################################
def test_child_stage_must_fit_in_the_grid() -> None:
    """坐标越界同样是内容写错，装配期就报出来。"""
    game = create_srpg_game(name="BuildTest")

    with pytest.raises(AssertionError, match="超出"):
        build_from_blueprint(
            game,
            _blueprint(root=_battlefield(children=[_camp(Position(x=5, y=0))])),
        )


###############################################################################
def test_two_children_cannot_share_a_cell() -> None:
    """一格一物：同一父舞台下坐标不得重复。"""
    game = create_srpg_game(name="BuildTest")
    root = _battlefield(
        children=[
            _camp(Position(x=1, y=1), name="舞台.营地"),
            _camp(Position(x=1, y=1), name="舞台.哨站"),
        ]
    )

    with pytest.raises(AssertionError, match="已被占用"):
        build_from_blueprint(game, _blueprint(root=root))


###############################################################################
def test_position_without_grid_parent_is_rejected() -> None:
    """父舞台没有网格，子舞台的位置就没有意义，别让它悄悄失效。"""
    game = create_srpg_game(name="BuildTest")
    settlement = _camp(Position(x=2, y=2), name="舞台.营地")
    settlement.children = [_camp(Position(x=0, y=0), name="舞台.铁匠铺")]

    with pytest.raises(AssertionError, match="没有网格"):
        build_from_blueprint(
            game,
            _blueprint(root=_battlefield(children=[settlement])),
        )


###############################################################################
def test_duplicate_names_are_rejected() -> None:
    """名字是 ECS 的索引键，重名会静默覆盖，必须在装配期拦住。"""
    game = create_srpg_game(name="BuildTest")
    duplicated = _blueprint(
        actors=[
            ActorBlueprint(
                name="角色.甲",
                system_message="角色.甲 的设定",
                components={"ActorComponent": {"current_stage": "舞台.营地"}},
            ),
            ActorBlueprint(
                name="角色.甲",
                system_message="角色.甲 的设定",
                components={"ActorComponent": {"current_stage": "舞台.营地"}},
            ),
        ]
    )

    with pytest.raises(AssertionError, match="重名实体"):
        build_from_blueprint(game, duplicated)


###############################################################################
def test_actor_on_undeclared_stage_is_rejected() -> None:
    """角色的所在舞台必须是蓝图声明过的舞台，否则游戏一开局就是悬空的。"""
    game = create_srpg_game(name="BuildTest")

    with pytest.raises(AssertionError, match="所在舞台不存在: 舞台.别处"):
        build_from_blueprint(
            game,
            _blueprint(actor_stage="舞台.别处"),
        )


###############################################################################
def test_prompt_must_contain_entity_name() -> None:
    """实体全名是路由契约，system_message 里缺了它就是内容写错。"""
    game = create_srpg_game(name="BuildTest")
    root = _battlefield(children=[_camp(Position(x=2, y=2))])
    root.system_message = "少了名字的设定"

    with pytest.raises(AssertionError, match="系统消息缺少实体名"):
        build_from_blueprint(game, _blueprint(root=root))


###############################################################################
def test_build_rejects_non_empty_game() -> None:
    """一局只构建一次，已有实体的游戏不能重复构建。"""
    game = create_srpg_game(name="BuildTest")
    build_from_blueprint(game, _blueprint())

    with pytest.raises(AssertionError, match="游戏中有实体"):
        build_from_blueprint(game, _blueprint())


###############################################################################
def test_actor_marker_carries_stage() -> None:
    """舞台归属写在组件里，不靠嵌套结构，读回来就是当初写下的值。"""
    game: SRPGGame = create_srpg_game(name="BuildTest")
    build_from_blueprint(game, _blueprint())

    actor = get_actor_entity(game, "角色.甲")
    assert actor is not None
    assert actor.get(ActorComponent).current_stage == "舞台.营地"
