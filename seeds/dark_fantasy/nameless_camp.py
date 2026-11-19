"""剧本「无名的营地」：一个世界、一棵舞台树、一个角色，作为开发与测试的起点。

舞台树只有两层：根是 5x5 的战场，营地位于其中一格。故事级设定（战役设定、全局规则、
世界职责）在 ``story`` 模块共用；这里只放本剧本专属的实体数据，状态一律写成组件数据。
"""

from ai_srpg.game.prompt_composer import compose_actor, compose_stage, compose_world
from ai_srpg.models import (
    ActorBlueprint,
    Blueprint,
    Position,
    StageBlueprint,
    WorldBlueprint,
)

from .story import CAMPAIGN_SETTING, GLOBAL_RULES, WORLD_ROLE_RULES

BATTLEFIELD_NAME = "舞台.战场"
STAGE_NAME = "舞台.营地"
BATTLEFIELD_GRID = {"width": 5, "height": 5}

#######################################################################################################################################
# 无名的体型：既进 prompt 的「基础体型」段，也是角色的初始外观
BASE_BODY = "年近三十的男性，肩宽而骨架分明，身形偏瘦但不单薄。身穿一件洗得发白的旧斗篷，缝制方式少见、边角磨损起毛，肤色偏浅。面容轮廓分明，下颌线条硬朗，眼下有淡淡的暗沉，眼睑低垂，目光沉静。手指细长，关节明显。"


def create_nameless() -> ActorBlueprint:
    """创建玩家角色——无名。"""

    actor = compose_actor(
        name="角色.无名",
        profile="""**历史**: 你醒来时想不起自己是谁，也想不起自己从哪儿来。你身上穿着一件不属于此地样式的旧斗篷，脑海深处只残留着一些断裂的碎片——那里没有魔法，也没有刀剑横行的荒野。你说不清那是什么地方，却清楚一件事：你不是这里的人。这件事你对谁都没有提过，也说不清。于是你给自己取了一个称呼：「无名」。把你从路边捡回来的，是个落魄的老佣兵，他给你起了名，也没多问，就这样把你带进了这一行。
**性格**: 你沉默，观察多于开口。面对陌生的事物不会慌乱，而是停下来，仔细看，仔细想，再决定怎么做。你不排斥危险，但也不会轻易莽撞。
**禁忌**: 你对任何人追问你的来历、强行拿走你身上仅有的东西、或强迫你去某个地方，都有本能的抵触。
**最爱**: 你发现自己喜欢坐在炉火边，听火舌舔过木柴的轻响，那时候周围很安静。""",
        base_body=BASE_BODY,
        campaign_setting=CAMPAIGN_SETTING,
        global_rules=GLOBAL_RULES,
    )
    actor.components = {
        "ActorComponent": {"current_stage": STAGE_NAME},
        "AppearanceComponent": {"base_body": BASE_BODY},
    }
    return actor


#######################################################################################################################################
def create_camp_stage() -> StageBlueprint:
    """创建极简营地：作为舞台与据点数据的起点。"""

    stage = compose_stage(
        name=STAGE_NAME,
        profile="""一处背风的营地。碎石围出一圈浅坑，余烬还带着一点温度；几件行囊靠在岩根，远处是通往荒野的旧道。
这里没有常驻的人，也没有可做的事，只是出发前与归来后短暂停留的地方。""",
        campaign_setting=CAMPAIGN_SETTING,
        global_rules=GLOBAL_RULES,
    )
    stage.components = {"StageComponent": {}}
    stage.position = Position(x=2, y=2)
    return stage


#######################################################################################################################################
def create_battlefield() -> StageBlueprint:
    """创建舞台树的根——战场：全局舞台，自带网格，营地摆在中央一格。"""

    stage = compose_stage(
        name=BATTLEFIELD_NAME,
        profile="""一片没有名字的旷野，被雨水与旧车辙切成方格状的地界。视野里没有明显的道路，
只有几处能在夜里分辨的轮廓：一段残墙、一片矮树林、以及远处没有灯火的平地。""",
        campaign_setting=CAMPAIGN_SETTING,
        global_rules=GLOBAL_RULES,
    )
    stage.components = {
        "StageComponent": {},
        "GlobalStageComponent": dict(BATTLEFIELD_GRID),
    }
    stage.children = [create_camp_stage()]
    return stage


#######################################################################################################################################
def create_starless_world() -> WorldBlueprint:
    """创建世界实体——无星长夜：叙事者与规则仲裁者，高于所有舞台。"""

    world = compose_world(
        name="世界.无星长夜",
        campaign_setting=CAMPAIGN_SETTING,
        global_rules=GLOBAL_RULES,
        role_rules=WORLD_ROLE_RULES,
    )
    world.components = {"WorldComponent": {}}
    return world


#######################################################################################################################################
def create_blueprint(game_name: str) -> Blueprint:
    """装配本剧本的蓝图；出厂闸门与提示词留痕由内容包统一处理。"""

    return Blueprint(
        name=game_name,
        campaign_setting=CAMPAIGN_SETTING,
        global_rules=GLOBAL_RULES,
        stage_tree=create_battlefield(),
        actors=[create_nameless()],
        worlds=[create_starless_world()],
    )


###############################################################################
__all__ = ["create_blueprint"]
