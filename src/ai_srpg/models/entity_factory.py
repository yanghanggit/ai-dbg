"""
游戏实体工厂模块。

这里只负责把内容侧的作者信息（设定、体型）拼成实体的 ``system_message``；组件
一律由内容侧显式声明，工厂不猜。

system prompt 段序原则：内容向的「游戏设定」「角色/舞台设定」「基础体型」等在前，
具备规则效果的「全局规则」在后——让 agent 先建立角色与世界观，最后读到必须遵守的规则。
"""

from . import ActorBlueprint, StageBlueprint, WorldBlueprint


#######################################################################################################################################
def create_actor(
    name: str,
    profile: str,
    base_body: str,
    campaign_setting: str,
    global_rules: str,
) -> ActorBlueprint:
    """
    创建一个角色蓝图实例，组装它的 system prompt。
    """

    assert name.strip() != "", "SRPG 游戏要求必须有角色名称(name)"
    assert profile.strip() != "", "SRPG 游戏要求必须有角色设定(profile)"
    assert base_body.strip() != "", "SRPG 游戏要求必须有角色体型(base_body)"
    assert (
        campaign_setting.strip() != ""
    ), "SRPG 游戏要求必须有游戏设定(campaign_setting)"
    assert global_rules.strip() != "", "SRPG 游戏要求必须有全局规则(global_rules)"

    return ActorBlueprint(
        name=name,
        system_message=f"""# {name}

你扮演角色: {name}

## 游戏设定

{campaign_setting}

## 角色设定

{profile}

### 基础体型

{base_body}

## 全局规则

{global_rules}""",
    )


#######################################################################################################################################
def create_stage(
    name: str,
    profile: str,
    campaign_setting: str,
    global_rules: str,
) -> StageBlueprint:
    """
    创建一个舞台蓝图实例，组装它的 system prompt。
    """

    assert name.strip() != "", "SRPG 游戏要求必须有舞台名称(name)"
    assert profile.strip() != "", "SRPG 游戏要求必须有舞台设定(profile)"
    assert (
        campaign_setting.strip() != ""
    ), "SRPG 游戏要求必须有游戏设定(campaign_setting)"
    assert global_rules.strip() != "", "SRPG 游戏要求必须有全局规则(global_rules)"

    return StageBlueprint(
        name=name,
        system_message=f"""# {name}

你扮演舞台: {name}

## 游戏设定

{campaign_setting}

## 舞台设定

{profile}

## 全局规则

{global_rules}""",
    )


#######################################################################################################################################
def create_world(
    name: str, campaign_setting: str, global_rules: str, role_rules: str
) -> WorldBlueprint:
    """
    创建一个世界蓝图实例，组装它的 system prompt。
    """

    assert name.strip() != "", "SRPG 游戏要求必须有世界名称(name)"
    assert (
        campaign_setting.strip() != ""
    ), "SRPG 游戏要求必须有游戏设定(campaign_setting)"
    assert global_rules.strip() != "", "SRPG 游戏要求必须有全局规则(global_rules)"
    assert role_rules.strip() != "", "SRPG 游戏要求必须有角色扮演规则(role_rules)"

    return WorldBlueprint(
        name=name,
        system_message=f"""# {name}

你扮演世界: {name}

## 游戏设定

{campaign_setting}

{role_rules}

## 全局规则

{global_rules}""",
    )


###############################################################################
__all__ = ["create_actor", "create_stage", "create_world"]
