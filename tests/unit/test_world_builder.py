"""蓝图装配的显式约束：类别标记、舞台归属、组件派生。

蓝图只给名字、``memories[0]`` 与组件数据；类别不靠枚举，而靠装配期要求实体
带对了标记组件——漏写就是内容写错，必须当场失败。
"""

from typing import Optional

import pytest

from ai_srpg.game.assembly import create_srpg_game
from ai_srpg.game.context import SRPGGame
from ai_srpg.game.entities import build_from_blueprint, get_actor_entity
from ai_srpg.models import (
    ActorBlueprint,
    ActorComponent,
    AppearanceComponent,
    Blueprint,
    StageBlueprint,
    WorldBlueprint,
)


###############################################################################
def _blueprint(
    *,
    actor_components: Optional[dict[str, dict[str, str]]] = None,
    stage_components: Optional[dict[str, dict[str, str]]] = None,
    actor_stage: str = "舞台.甲",
) -> Blueprint:
    return Blueprint(
        name="BuildTest",
        campaign_setting="设定",
        global_rules="规则",
        stages=[
            StageBlueprint(
                name="舞台.甲",
                system_message="舞台.甲 的设定",
                components=(
                    {"StageComponent": {}}
                    if stage_components is None
                    else stage_components
                ),
            )
        ],
        actors=[
            ActorBlueprint(
                name="角色.甲",
                system_message="角色.甲 的设定",
                components=(
                    {"ActorComponent": {"current_stage": actor_stage}}
                    if actor_components is None
                    else actor_components
                ),
            )
        ],
        world_entities=[
            WorldBlueprint(
                name="世界.甲",
                system_message="世界.甲 的设定",
                components={"WorldComponent": {}},
            )
        ],
    )


###############################################################################
def test_components_land_on_the_entity_verbatim() -> None:
    """组件数据原样进 ECS，装配期不猜任何字段。"""
    game = create_srpg_game(name="BuildTest")
    blueprint = _blueprint(
        actor_components={
            "ActorComponent": {"current_stage": "舞台.甲"},
            "AppearanceComponent": {"base_body": "瘦削"},
        },
        stage_components={"StageComponent": {}},
    )

    build_from_blueprint(game, blueprint, user_name="alice")

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
                "ActorComponent": {"current_stage": "舞台.甲"},
                "AppearanceComponent": {"base_body": "瘦削"},
            }
        ),
        user_name="alice",
    )

    actor = get_actor_entity(game, "角色.甲")
    assert actor is not None
    appearance = actor.get(AppearanceComponent)
    assert appearance.appearance == appearance.base_body == "瘦削"


###############################################################################
def test_missing_actor_marker_is_rejected() -> None:
    """没挂 ``ActorComponent`` 的角色只是一个普通实体，必须当场报错。"""
    game = create_srpg_game(name="BuildTest")

    with pytest.raises(AssertionError, match="缺少标记组件 ActorComponent"):
        build_from_blueprint(
            game,
            _blueprint(
                actor_components={"AppearanceComponent": {"base_body": "瘦削"}},
            ),
            user_name="alice",
        )


###############################################################################
def test_missing_stage_marker_is_rejected() -> None:
    """没挂 ``StageComponent`` 的舞台不会被下游认出来，同样当场报错。"""
    game = create_srpg_game(name="BuildTest")

    with pytest.raises(AssertionError, match="缺少标记组件 StageComponent"):
        build_from_blueprint(
            game,
            _blueprint(stage_components={}),
            user_name="alice",
        )


###############################################################################
def test_actor_on_undeclared_stage_is_rejected() -> None:
    """角色的所在舞台必须是蓝图声明过的舞台，否则游戏一开局就是悬空的。"""
    game = create_srpg_game(name="BuildTest")

    with pytest.raises(AssertionError, match="所在舞台不存在: 舞台.乙"):
        build_from_blueprint(
            game,
            _blueprint(actor_stage="舞台.乙"),
            user_name="alice",
        )


###############################################################################
def test_prompt_must_contain_entity_name() -> None:
    """实体全名是路由契约，system_message 里缺了它就是内容写错。"""
    game = create_srpg_game(name="BuildTest")
    blueprint = _blueprint()
    blueprint.stages[0].system_message = "少了名字的设定"

    with pytest.raises(AssertionError, match="系统消息缺少实体名"):
        build_from_blueprint(game, blueprint, user_name="alice")


###############################################################################
def test_build_rejects_non_empty_game() -> None:
    """一局只构建一次，已有实体的游戏不能重复构建。"""
    game = create_srpg_game(name="BuildTest")
    build_from_blueprint(game, _blueprint(), user_name="alice")

    with pytest.raises(AssertionError, match="游戏中有实体"):
        build_from_blueprint(game, _blueprint(), user_name="bob")


###############################################################################
def test_actor_marker_carries_stage() -> None:
    """舞台归属写在组件里，不靠嵌套结构，读回来就是当初写下的值。"""
    game: SRPGGame = create_srpg_game(name="BuildTest")
    build_from_blueprint(game, _blueprint(), user_name="alice")

    actor = get_actor_entity(game, "角色.甲")
    assert actor is not None
    assert actor.get(ActorComponent).current_stage == "舞台.甲"
