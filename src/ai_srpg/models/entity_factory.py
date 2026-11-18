"""
游戏实体工厂模块。

system prompt 段序原则：内容向的「游戏设定」「角色/舞台设定」「基础体型」等在前，
具备规则效果的「全局规则」在后——让 agent 先建立角色与世界观，最后读到必须遵守的规则。
"""

from . import (
    Actor,
    ActorType,
    Stage,
    StageType,
    World,
)


#######################################################################################################################################
def create_actor(
    name: str,
    actor_type: ActorType,
    profile: str,
    base_body: str,
    campaign_setting: str,
    global_rules: str,
) -> Actor:
    """
    创建一个游戏角色(Actor)实例。
    """

    assert name.strip() != "", "SRPG 游戏要求必须有角色名称(name)"
    assert profile.strip() != "", "SRPG 游戏要求必须有角色设定(profile)"
    assert base_body.strip() != "", "SRPG 游戏要求必须有角色设定(base_body)"
    assert (
        campaign_setting.strip() != ""
    ), "SRPG 游戏要求必须有游戏设定(campaign_setting)"
    assert global_rules.strip() != "", "SRPG 游戏要求必须有全局规则(global_rules)"

    actor = Actor(
        name=name,
        type=actor_type,
        profile=profile,
        base_body=base_body,
        system_message="",
    )

    # 系统提示词词
    actor.system_message = f"""# {actor.name}

你扮演角色: {actor.name}

## 游戏设定

{campaign_setting}

## 角色设定

{profile}

### 基础体型

{base_body}

## 全局规则

{global_rules}"""

    return actor


#######################################################################################################################################
def create_stage(
    name: str,
    stage_type: StageType,
    profile: str,
    campaign_setting: str,
    global_rules: str,
) -> Stage:
    """
    创建一个游戏舞台(Stage)实例。
    """

    assert name.strip() != "", "SRPG 游戏要求必须有舞台名称(name)"
    assert profile.strip() != "", "SRPG 游戏要求必须有舞台设定(profile)"
    assert (
        campaign_setting.strip() != ""
    ), "SRPG 游戏要求必须有游戏设定(campaign_setting)"
    assert global_rules.strip() != "", "SRPG 游戏要求必须有全局规则(global_rules)"

    # 创建舞台实例
    stage = Stage(
        name=name,
        type=stage_type,
        profile=profile,
        system_message="",
        actors=[],
    )

    # 系统提示词词
    stage.system_message = f"""# {stage.name}

你扮演舞台: {stage.name}

## 游戏设定

{campaign_setting}

## 舞台设定

{profile}

## 全局规则

{global_rules}"""

    return stage


#######################################################################################################################################


def create_world(
    name: str, campaign_setting: str, global_rules: str, role_rules: str
) -> World:
    """
    创建一个世界(World)实例。
    """

    assert name.strip() != "", "SRPG 游戏要求必须有世界名称(name)"
    assert (
        campaign_setting.strip() != ""
    ), "SRPG 游戏要求必须有游戏设定(campaign_setting)"
    assert global_rules.strip() != "", "SRPG 游戏要求必须有全局规则(global_rules)"
    assert role_rules.strip() != "", "SRPG 游戏要求必须有角色扮演规则(role_rules)"

    # 创建世界实例
    world = World(
        name=name,
        system_message="",
        components={},
    )

    # 系统提示词词
    world.system_message = f"""# {world.name}

你扮演世界: {world.name}

## 游戏设定

{campaign_setting}

{role_rules}

## 全局规则

{global_rules}"""

    return world


###############################################################################
__all__ = ["create_actor", "create_stage", "create_world"]
