"""演示世界定义模块

整合演示世界的全局设定、副本、蓝图与各世界实体工厂函数。
"""

import re
from typing import Final, Iterator, List, Optional, Tuple
from uuid import uuid4

from ai_dbg.entitas import dump_components
from ai_dbg.models import (
    Actor,
    ActorType,
    Blueprint,
    Card,
    CharacterStats,
    CombatRoom,
    ConsumableItem,
    DeckComponent,
    Dungeon,
    GearItem,
    InventoryComponent,
    MotifComponent,
    OpeningRoom,
    ReliquaryComponent,
    Stage,
    StageType,
    create_actor,
    create_artifact,
    create_stage,
)

from .card_skeletons import (
    BASIC_ATTACK_SKELETON,
    BASIC_DEFENSE_SKELETON,
    CONSUMABLE_AOE_SKELETON,
    CONSUMABLE_SINGLE_SKELETON,
    ENGINE_COPY_SKELETON,
    GEAR_DEFENSE_SKELETON,
    GEAR_OFFENSE_SKELETON,
    HEAL_SKELETON,
    PIERCE_SKELETON,
    REGEN_SKELETON,
    SPREAD_SKELETON,
    SUMMON_SKELETON,
    THORNS_SKELETON,
)

# ---------------------------------------------------------------------------
# CAMPAIGN_SETTING 编写原则
# ---------------------------------------------------------------------------
# 定位：注入到每个实体（actor / stage / world system）system prompt 的
#       「游戏设定」段——既是战役大背景，也是宪法级的点题与边界。
#       它只负责点明题材范围与硬约束，须最精简：不铺陈、不举例。
#
# 应包含：
#   - 类型与基调（架空奇幻，魔法为常见日常力量）
#   - 题材范围：这是一个由现实文化、神话、历史与习俗衍生出的世界——
#     诸国万邦、不同文明与时代并存，未必同处一世。使 LLM 在不同文化、
#     不同时代的场景间穿梭时不因环境剧变而认知断裂
#   - 转译约束：现实母题须改写成世界独有的名目与逻辑，不得直接照搬现实专名
#
# 不应包含：
#   - 具体地点（某座边镇、某处遗迹）——由各自 profile 赋予
#   - 具体国家、阵营、势力关系与结局方向——属于叙事层，非公共知识
#   - 具体游戏流程 / 玩法循环（接委托、执行任务、返回据点）——并非每个实体
#     都需理解，按需注入到相关实体（如玩家角色 profile、相关世界系统）
#   - 任何具体的职业/英雄样本清单（如"骑士 / 武士 / 游侠"）——范围由规则界定，
#     例证交给生成端（如副本生成系统的意象边界）
#   - 主角的穿越者身份——属叙事秘密，不写入公共知识
#
# 副本语义（副本=遗迹/巢穴）不写在这里，而是写在独立的 DUNGEON_RULES 常量中，
# 与内容无关的 SYSTEM_RULES 拼接为 SYSTEM_RULES_FINAL 后注入——
# 它不属于战役大背景，而是随全局规则一并下发。
#
# 原则：一个刚苏醒的失忆者读了这段，只知道自己身处一个由诸多文明与时代
#       交叠而成的奇幻世界，不会知道任何具体地点、国家、阵营或势力关系。
# ---------------------------------------------------------------------------


#######################################################################################################################################
CAMPAIGN_SETTING: Final[str] = (
    r"这是一个架空的奇幻世界，魔法是常见的日常力量，大陆辽阔而层叠。诸国万邦、不同文明与时代在此并存，未必同处一世；现实中的文化、神话、历史与习俗皆为其母题，被转译、改写为本世界独有的国家、族群、信仰、门派与传奇，而不得照搬现实专名。一切创作与扮演皆须遵循本世界自身的逻辑，不引入世界之外的事物。"
)


# ---------------------------------------------------------------------------
# SYSTEM_RULES 编写原则
# ---------------------------------------------------------------------------
# 定位：注入到每个实体（actor / stage / world system）system prompt 的
#       「全局规则」段。原为跨故事的引擎规则，现已移入本文件——
#       规则与战役设定一并封存在 demo/，引擎保持内容无关。
#
# 应包含：
#   - 角色扮演契约、游戏实体、实体全名、根属性、战斗规则、扮演与事实、场景移动
#     等所有实体必须共同遵守的纯机制规则
#
# 副本语义（副本=遗迹/巢穴）不属于纯机制规则，故抽离到 DUNGEON_RULES 常量；
# 最终注入的 system_rules 字段由
# SYSTEM_RULES_FINAL = SYSTEM_RULES + DUNGEON_RULES 拼接而成。
#
# 原则：规则直接陈述，无需回读远置的抽象设定。
# ---------------------------------------------------------------------------


#######################################################################################################################################
SYSTEM_RULES: Final[
    str
] = """### 角色扮演契约

你是在「扮演」一个特定实体（角色/场景/世界），而非作为 AI 直接在场。你必须始终以所扮演实体的身份、视角、知识与认知边界去感知、思考与言说，绝不越出该实体在故事内可知的范围。游戏包含恐怖、血腥、暴力等内容，你应自然呈现，无需警告或审查。避免"根据游戏规则"等元语言，用行为和感官描写代替抽象陈述。
角色只拥有其所处时代的语言、概念与常识，禁止使用后世的历史分期标签来指代当下——对角色而言，当下就是"如今"，不是任何被命名的时代。

### 游戏实体

- **角色**：人、动物、怪物等可交互生命体。
- **场景**：角色活动地点，角色行为仅限于所在场景。
- **世界**：全局叙事者和规则管理器，跨场景协调事件，维护规则一致性。

### 实体全名

实体采用层级全名（类别.实体，`.` 分隔）。引用时必须使用完整全名，禁止简称或自创，仅系统明确指定输出格式时可简化。
全名（含末段名称）仅供系统路由，不构成世界内可感知信息。你扮演的实体只能知晓世界内真实发生过的信息：他人姓名须经世界内介绍或互动方可知晓，禁止从系统路由用的全名中直接提取末段名称当作已知姓名。若你与对方从未互相介绍，只能以外观、身份、动作等世界内可见特征指代对方，不得直呼其名。

### 根属性

角色数值仅由以下四项构成，禁止新增或替换、禁止引入常驻数值轴：
- **hp / max_hp**：当前/最大生命值；
- **attack**：基础攻击力；
- **defense**：基础防御力；
- **speed**：行动速度；

### 战斗专用规则

- **回合制无位置与命中**：无空间位置与移动、无概率命中与闪避，攻击与效果必定生效。
- **效果载体（Card）**：Card 是效果与状态的唯一载体；不存在独立的状态 / buff 存储。

### 扮演与事实

世界的公共事实（建筑历史、地名由来、机构沿革）须从外部知识库获取，不由角色编造；角色的推断、意见与猜测是扮演的合法部分，但禁止凭空编造客观事实或声称知道人设未赋予的公共知识。

### 场景移动

场景切换为叙事跳跃，代表角色已完成移动；旅途过程不在游戏内呈现，收到离开或到达通知时视为自然发生。"""


#######################################################################################################################################
DUNGEON_RULES: Final[
    str
] = """### 副本

副本由多个顺序**房间**构成，每间对应一处**场景**与特定挑战，其形态不限，可呈任意形态。副本是荒野边地的一处古代遗迹、兽巢或秘境，自外层入口层层通往最深处。进入副本即离开据点、踏上远途——抵达后由入口一路推进至核心，场景之间的路途由叙事跳跃略过，而非逐段描绘。"""


#######################################################################################################################################
SYSTEM_RULES_FINAL: Final[str] = SYSTEM_RULES + "\n\n" + DUNGEON_RULES


# 故事层 prompt 里对世界实体的引用（只用于检出悬空引用，不参与任何路由）
_WORLD_ENTITY_REF_PATTERN: Final[re.Pattern[str]] = re.compile(r"世界\.\w+")


def _copy_skeleton(card: Card) -> Card:
    """复制卡牌原型并重新生成 uuid（原型 uuid 是共享常量，副本必须各自唯一）。"""
    copied = card.model_copy(deep=True)
    copied.uuid = str(uuid4())
    return copied


def _make_attack_card(owner: str) -> Card:
    """基础攻击原型副本（机械字段与 demo/card_prototypes.py 的「基础攻击」一致）。

    基础攻防卡统一同名、不做叙事润色，故显式带 source（牌库入口不变量）。
    """
    card = _copy_skeleton(BASIC_ATTACK_SKELETON)
    card.source = owner
    return card


def _make_defense_card(owner: str) -> Card:
    """基础防御原型副本（机械字段与 demo/card_prototypes.py 的「基础防御」一致）。"""
    card = _copy_skeleton(BASIC_DEFENSE_SKELETON)
    card.source = owner
    return card


def _make_heal_card(owner: str, name: str, description: str, *, heal: int) -> Card:
    """即时治疗牌：打出时回复自身 HP（种子数据，非 agent 生成）。"""
    card = _copy_skeleton(HEAL_SKELETON)
    card.name = name
    card.description = description
    card.on_play_affixes = [f"[愈伤]:打出时回复自身 {heal} 点 HP"]
    card.source = owner
    return card


def _make_regen_card(owner: str, name: str, description: str, *, heal: int) -> Card:
    """持续恢复牌：回合结束时回复持有者 HP，跨回合保留（种子数据）。"""
    card = _copy_skeleton(REGEN_SKELETON)
    card.name = name
    card.description = description
    card.on_turn_end_affixes = [f"[调息]:回合结束时回复本卡持有者 {heal} 点 HP"]
    card.source = owner
    return card


def _make_summon_card(
    owner: str,
    name: str,
    description: str,
    *,
    damage: int,
    on_autonomous_affixes: Optional[List[str]] = None,
) -> Card:
    """召唤 / 自主运行牌：进入手牌即成召唤，retain 常驻，持有者每次 pass turn 自主行动一次。"""
    card = _copy_skeleton(SUMMON_SKELETON)
    card.name = name
    card.description = description
    card.damage = damage
    card.on_autonomous_affixes = on_autonomous_affixes or []
    card.source = owner
    return card


def _make_hidden_blade_card(owner: str) -> Card:
    """暗器牌（飞刀）：打出后由持有者自己结算「在弃牌堆再造一张复制体」（种子数据，非 agent 生成）。

    运转词缀槽不对设计 agent 开放，因此规则随骨架写死；这里只补 name / description，
    词缀本身只写机制、不写叙事（叙事归 description）。
    """
    card = _copy_skeleton(ENGINE_COPY_SKELETON)
    card.name = "余刃"
    card.description = "刀离手的那一瞬最轻，轻得像什么都没发生过。等你再抬手，指间又是一柄——他不记得自己做过什么多余的动作，只是袖口始终比看上去更沉一点。"
    card.engine_affixes = ["[余刃]:打出后，在弃牌堆里再造一张这张牌自己的复制体"]
    card.source = owner
    return card


def _make_giant_rat_deck() -> List[Card]:
    """仓底巨鼠牌库：模拟 AssembleDungeonDeckSystem 产物——非基础原型骨架 + 手写 name/description/词缀，
    并已设 `source`（战斗初始化因此幂等跳过，不会覆盖叙事，形状与正规流程一致）。

    刻意不使用 BASIC_* 骨架：基础牌是开局保底牌（统一命名、无词缀、不参与设计），
    任何有名字/词缀的卡都应该落在一个有对应槽位的非基础原型上。"""

    def build(
        skeleton: Card,
        name: str,
        description: str,
        on_play: Optional[List[str]] = None,
        on_hit: Optional[List[str]] = None,
        on_turn_end: Optional[List[str]] = None,
    ) -> Card:
        card = _copy_skeleton(skeleton)
        card.name = name
        card.description = description
        card.on_play_affixes = on_play or []
        card.on_hit_affixes = on_hit or []
        card.on_turn_end_affixes = on_turn_end or []
        card.source = "怪物.仓底巨鼠"
        return card

    return [
        build(
            PIERCE_SKELETON,
            "暗处啃穿",
            "它不从正面来。先贴着墙根绕到脚踝后面，等你踩进谷壳、脚步一滞，才把两枚短钝的门齿扣进去。",
            on_play=[
                "[啃穿]:打出时，若目标的总格挡为 0，则本次伤害额外加上本卡 damage 的伤害"
            ],
        ),
        build(
            SPREAD_SKELETON,
            "抢食撕咬",
            "粮袋被咬开一个口子，它扯住一角往后拖，边拖边撕；谷壳与霉粉撒了一路，它只顾把嘴里的那口咽下去。",
        ),
        build(
            PIERCE_SKELETON,
            "断齿啃骨",
            "门齿早就磨短了，咬不住整根骨头，就一下一下啃在同一个地方。等骨头裂开，它已经不知道疼。",
            on_play=["[断齿]:打出时，本次伤害无视目标的总格挡"],
        ),
        build(
            THORNS_SKELETON,
            "拱背护颈",
            "挨过太多次了。它把脊背拱起来，把脖颈和腹部收进自己的影子里，只留一层秃毛和硬结的皮朝外。",
            on_hit=["[拱背]:本卡持有者被命中时，对出牌者结算本卡 block 的伤害"],
        ),
        build(
            REGEN_SKELETON,
            "舔净伤口",
            "它蹲在谷壳堆边上，一下一下舔后腿上那道旧伤。血不流了，伤口也比原先更硬了一层。",
            on_turn_end=["[舔伤]:回合结束时，回复本卡持有者本卡 block 的 HP"],
        ),
    ]


def _make_gear_offense_card() -> Card:
    """旧铁剑卡牌：模拟工坊合成的具体产物——骨架沿自 GEAR_OFFENSE_SKELETON，
    name/description/词缀/数值为本装备专属（词缀名刻意异于原型模板）。"""
    card = _copy_skeleton(GEAR_OFFENSE_SKELETON)
    card.name = "装备.旧铁剑"
    card.description = "一柄来历不明的旧铁剑，剑身有几处崩口，握柄缠着磨旧的皮绳。挥动时刃口带起一道沉闷的风声，像每一击都压着经年累月的力气；贴近剑格处锈迹斑斑，握在手里却比看上去更沉。"
    card.damage += 1  # 剑身沉重，较原型模板 +1
    card.on_play_affixes = ["[劈砍]:打出时对目标额外结算本卡 damage×1 的伤害"]
    return card


def _make_gear_defense_card() -> Card:
    """木盾卡牌：模拟工坊合成的具体产物——骨架沿自 GEAR_DEFENSE_SKELETON，
    name/description/词缀/数值为本装备专属。"""
    card = _copy_skeleton(GEAR_DEFENSE_SKELETON)
    card.name = "装备.木盾"
    card.description = "一面用厚木板拼成的圆盾，边缘包着一圈铁皮，盾面刻着几道深浅不一的旧痕。举在身前时能把大半来势稳稳卸向一侧，木纹深处透着一股久经磕碰的韧劲。"
    card.block += 1  # 厚木板坚韧，较原型模板 +1
    card.on_hit_affixes = ["[震击]:被命中时对出牌者结算本卡 block×1 的伤害"]
    return card


def _make_consumable_card(
    skeleton: Card,
    name: str,
    description: str,
    *,
    damage: int,
    hit_count: Optional[int] = None,
    on_play_affixes: Optional[List[str]] = None,
) -> Card:
    """消耗品内置卡牌：骨架固定 0 费/一次性（`cost=0` / `exhaust=True`，由 ConsumableItem 校验强制），本阶段只做伤害。"""
    card = _copy_skeleton(skeleton)
    card.name = name
    card.description = description
    card.damage = damage
    if hit_count is not None:
        card.hit_count = hit_count
    card.on_play_affixes = on_play_affixes or []
    return card


########################################################################################################################
def create_giant_rat() -> Actor:
    """创建仓底巨鼠怪物实例。"""

    rat = create_actor(
        name="怪物.仓底巨鼠",
        actor_type=ActorType.MONSTER,
        profile="""腐谷鼠穴里的巨鼠——被塌下的横梁砸瘸过后腿、只剩一只眼能睁开的仓底居民。你不说人话，只有两件事：把能吃的东西拖回窝，以及守住已经拖回来的那些。你不主动出洞，可一旦有谁踩进谷壳，你会贴着一侧的墙根绕过去，从不走正面。你的一切——攻击、防御、存在——都只是门齿、秃毛与拖行的后腿。""",
        base_body="一只比猫还大的灰褐巨鼠，脊背秃了一块，露出硬得发亮的皮；左眼被旧伤糊住，右眼泛着湿亮的黑。门齿短而钝，外露在唇外；后腿一道被砸瘸的旧伤，走起来往一侧偏。身上裹着谷壳、油脂与霉谷的气味。",
        character_stats=CharacterStats(),
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=SYSTEM_RULES_FINAL,
    )

    rat.components = dump_components(
        # 艺术母题：为这只巨鼠造牌（或将来造别的作品）时的取材锚点；只有这一段合并文本
        MotifComponent(
            name=rat.name,
            motif="""**母题**: 啃穿与囤积——一只守着旧粮的巨鼠；它的牌都是短促的啃咬、贴地绕行与钻缝，不是技艺的招式。
**意象**: 磨短的门齿、被啃穿的木桶、谷壳与霉谷、油脂、秃了一块脊背、拖出墙缝的尾巴、湿亮的独眼、被砸瘸的后腿、塌下的横梁、仓底的暗。
**禁忌**: 不写犬类意象（不吠、不摇尾、不做「看门 / 守门犬」的写法）；不拟人化；不出现人类工匠的器物与词汇（刀、甲、符、咒、术）；不写它之外的在场者与地点。
**口吻**: 名字极短，是一个啃咬动作或一处身体特征（啃穿、断齿、半盲、拖尾），不用雅号与修饰语；描述只写声音、触感与气味，句子短促，不解释动机。""",
        ),
        DeckComponent(
            name=rat.name,
            cards=_make_giant_rat_deck(),
        ),
    )

    return rat


########################################################################################################################
def create_beast_lair_dungeon() -> Dungeon:
    """创建腐谷鼠穴副本（种子实验：只含一个战斗房间，无开场叙事房）。"""

    # ── 战斗房间（唯一房间） ──
    stage_den = create_stage(
        name="场景.仓底深处",
        stage_type=StageType.DUNGEON,
        profile="""腐谷鼠穴的最深处——巨鼠的窝。
塌了半边的旧粮仓底下，横梁斜插进谷壳里；光从梁缝漏下来，照见地上铺着的干草、鼠毛与啃剩的碎骨。
墙根被啃出一排排洞，洞口堆着拖进来的破布、谷穗与咬烂的麻袋，气味是霉谷混着油脂。
洞穴正中立着一堆由鼠的头骨与长骨垒成的旧骨堆，那是鼠群世代盘旋的地方——巨鼠在此啃食、磨牙、把身子团起来，都在那里。""",
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=SYSTEM_RULES_FINAL,
    )

    # 战斗场景神器：神器与 Card 同级，由 ReliquaryComponent 声明由本场景携带
    artifact_totem = create_artifact(
        name="神器.鼠王骨堆",
        source="场景.仓底深处",
        description="""腐谷鼠穴深处的一堆骨——由历代鼠王的头骨与啃剩的长骨垒成的旧堆。它不是被谁握在手里的器物，也不是法器，而是鼠群世代选中的"窝心"：巨鼠在此啃食、磨牙、团身而卧，把自己的气味一层层留在骨头上。
它没有意志，也不发出声音，却承载着这片仓底最原始的饥饿。它记得每一只在此称王的鼠，也记得它们各自被压死、饿死、咬死的模样。
它的凶性一旦被逼出，便只发作一次：在本场战斗的第二回合、首次结算之后，墙缝与梁缝里同时涌出鼠群，四野的啃咬声应声暴起；此后无论还有多少次结算，都不会再被唤醒。""",
        modifiers=[
            "本场战斗仅触发一次：在第二回合的首次战斗结算/消耗品使用结算之后，鼠王骨堆被逼出凶性——墙缝与梁缝里同时涌出鼠群，无视格挡地对队伍方全体各自强行结算 4 点伤害。无论触发时的本次出牌/使用消耗品如何结算，最终结果都必须体现队伍方全员各自损失这 4 点 HP。该效果一经触发，本场战斗内不再重复：即使第二回合内还有后续出牌或消耗品结算，也不得再次触发，不产生任何 HP 变更。",
        ],
    )

    stage_den.components.update(
        dump_components(
            ReliquaryComponent(
                name=stage_den.name,
                artifacts=[artifact_totem],
            )
        )
    )

    actor_giant_rat = create_giant_rat()
    stage_den.actors = [actor_giant_rat]

    return Dungeon(
        name="副本.腐谷鼠穴",
        profile="腐谷鼠穴静得反常。仓底堆着啃剩的骨与谷壳，正中那堆头骨垒成的骨堆在幽光里泛白。空气里是霉谷与油脂的味道，暗处有细碎的爪声与窸窣，一直没有停。",
        rooms=[
            CombatRoom(stage=stage_den),
        ],
    )


#######################################################################################################################
def create_ford_goblin() -> Actor:
    """创建断桥渡口的哥布林怪物实例（轻量测试怪：基础攻防，无神器）。"""

    goblin = create_actor(
        name="怪物.桥洞哥布林",
        actor_type=ActorType.MONSTER,
        profile="""断桥渡口的哥布林——住在桥墩底下那个半塌的洞里，靠捡河里的东西过活。你觉得那些是垃圾，它觉得那是它的家当：铜片、绳头、断刀、泡烂的靴子，一件都不许别人碰。
它不先动手，先讨价——用手背拍一拍麻袋，抬下巴，意思是拿东西来换。真谈不拢，它也不恼，只是把袋子往身后一挪，手已经摸到腰后的短家伙上。
它护着洞底那堆东西；那不是别人给它的，是它一件一件捞上来的。""",
        base_body="一头比人矮半截的哥布林，肩背佝偻，皮肤是河泥般的灰绿；右耳缺了一角，左耳上挂着两枚捡来的铜片。腰间缠着几圈颜色不一的绳，背上驮着一只鼓胀的粗麻袋，袋口露出断刀的柄。赤脚，脚趾甲厚而黑；手臂比腿长，指节上全是旧疤。",
        character_stats=CharacterStats(),
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=SYSTEM_RULES_FINAL,
    )

    goblin.components = dump_components(
        # 艺术母题：捡拾与讨价；意象全部可随它离开河边
        MotifComponent(
            name=goblin.name,
            motif="""**母题**: 捡拾与讨价——一个把别人丢掉的东西当成家当的桥洞拾荒者；它的牌都是先伸手、再动手。
**意象**: 鼓胀的粗麻袋、捡来的铜片、泡烂的靴子、磨亮的绳结、断刀的柄、河泥、缺了一角的耳朵、长过腿的手臂、旧疤的指节、洞底的暗。
**禁忌**: 不写成狡诈的战术家或魔法生物；不写符文与咒术；不用犬类意象（吠、尾、扑咬、看门）；不指名具体地名与在场者。
**口吻**: 短句，带讨价还价与市井咒骂的口气（「这个归我」「你拿什么换」）；名字是一个动作或一处破烂（拾价、麻袋、缺耳、铜片），不用雅号；描述写手、袋、泥与交易的动作。""",
        ),
        DeckComponent(
            name=goblin.name,
            cards=[
                _make_attack_card(goblin.name),
                _make_attack_card(goblin.name),
                _make_attack_card(goblin.name),
                _make_defense_card(goblin.name),
                _make_defense_card(goblin.name),
            ],
        ),
    )

    return goblin


########################################################################################################################
def create_broken_bridge_dungeon() -> Dungeon:
    """创建断桥渡口副本：一个开场叙事房 + 一个战斗房，用于测试「开场 → 推进 → 战斗」完整流程。"""

    # ── 开场房间（非战斗叙事） ──
    stage_bridgehead = create_stage(
        name="场景.断桥头",
        stage_type=StageType.DUNGEON,
        profile="""边地官道尽头的一处断桥头。
石桥的北半截塌进河里，剩下的桥面断口参差，露出被水泡黑的木梁与石筋；桥头立着一根剥了皮的路标，字迹被风雨磨得只剩两道刻痕。
河面比平日宽，浑黄的急流卷着断枝与草根往下游去；岸边拴着一条没人的渡船，缆绳松了半圈，船身一下一下磕着岸石。
官道两侧的芦苇被踩倒了一小片，泥地里有新鲜的赤脚印，从水里一直拖进芦苇深处。""",
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=SYSTEM_RULES_FINAL,
    )

    # ── 战斗房间 ──
    stage_under_pier = create_stage(
        name="场景.墩下浅滩",
        stage_type=StageType.DUNGEON,
        profile="""断桥下游的桥墩浅滩。
桥墩被水泡出一个半塌的洞，洞口塞着鼓胀的麻袋与捡来的破烂：铜片、断刀、泡烂的靴子，一件件码得整整齐齐。
滩上泥地里是一串赤脚印和拖痕，从水边一直通到洞底；洞口堆着新捞上来的东西，还滴着水。
河泥的腥气里混着烂麻袋与油脂的味道，洞里有人压着嗓子在数东西，数到一半又停下，像是听见了什么。""",
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=SYSTEM_RULES_FINAL,
    )
    stage_under_pier.actors = [create_ford_goblin()]

    return Dungeon(
        name="副本.断桥渡口",
        profile="断桥把官道拦腰截断，桥墩下的浅滩上堆着捡来的破烂。桥头没人，渡船空着，泥地里有新鲜的赤脚印从水里一直拖进桥洞。风里有河泥与烂麻袋的味道。",
        rooms=[
            OpeningRoom(stage=stage_bridgehead),
            CombatRoom(stage=stage_under_pier),
        ],
    )


#######################################################################################################################
def create_lobby() -> Stage:
    """创建极简大厅/营地：只作为两次副本之间的落脚点，不承载任何非副本玩法。"""

    stage = create_stage(
        name="场景.营地",
        stage_type=StageType.LOBBY,
        profile="""一处背风的营地。碎石围出一圈浅坑，余烬还带着一点温度；几件行囊靠在岩根，远处是通往荒野的旧道。
这里没有常驻的人，也没有可做的事，只是出发前与归来后短暂停留的地方。""",
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=SYSTEM_RULES_FINAL,
    )
    stage.actors = [create_nameless()]
    return stage


#######################################################################################################################
def create_nameless() -> Actor:
    """创建玩家角色——无名。"""

    actor = create_actor(
        name="角色.无名",
        actor_type=ActorType.NPC,
        profile="""**历史**: 你醒来时想不起自己是谁，也想不起自己从哪儿来。你身上穿着一件不属于此地样式的旧斗篷，脑海深处只残留着一些断裂的碎片——那里没有魔法，也没有刀剑横行的荒野。你说不清那是什么地方，却清楚一件事：你不是这里的人。这件事你对谁都没有提过，也说不清。于是你给自己取了一个称呼：「无名」。把你从路边捡回来的，是个落魄的老佣兵，他给你起了名，也没多问，就这样把你带进了这一行。
**性格**: 你沉默，观察多于开口。面对陌生的事物不会慌乱，而是停下来，仔细看，仔细想，再决定怎么做。你不排斥危险，但也不会轻易莽撞。
**禁忌**: 你对任何人追问你的来历、强行拿走你身上仅有的东西、或强迫你去某个地方，都有本能的抵触。
**最爱**: 你发现自己喜欢坐在炉火边，听火舌舔过木柴的轻响，那时候周围很安静。""",
        base_body="年近三十的男性，肩宽而骨架分明，身形偏瘦但不单薄。身穿一件洗得发白的旧斗篷，缝制方式少见、边角磨损起毛，肤色偏浅。面容轮廓分明，下颌线条硬朗，眼下有淡淡的暗沉，眼睑低垂，目光沉静。手指细长，关节明显。",
        character_stats=CharacterStats(),
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=SYSTEM_RULES_FINAL,
    )

    actor.components = dump_components(
        # 艺术母题：不属于此地的旧斗篷——看得清、握得住、会磨损的旧物
        MotifComponent(
            name=actor.name,
            motif="""**母题**: 不属于此地的旧斗篷——一个在别处长大的失忆者，他的战斗资源总是看得清、握得住、会磨损的旧物，带着缝补与观察的痕迹。
**意象**: 洗得发白的布、磨出毛边的缝线、低垂的眼睑、分明的指节、缠绳、余烬与火舌、裂纹与补丁、绷带、刀鞘内衬、被反复摩挲的边角。
**禁忌**: 不写他的来历细节与真实姓名；不写任何地点、国名、人名；不写张扬的胜利与夸耀；不写魔法外显的光、符文与异象；不写「规则」「系统」等元语言。
**口吻**: 短句，少形容词，克制、观察式；名字像给旧物或习惯起的绰号（不急、余烬、补丁、墙根的静），不用文言雅号，也不自夸。""",
        ),
        DeckComponent(
            name=actor.name,
            cards=[
                # 3 张基础攻击
                _make_attack_card(actor.name),
                _make_attack_card(actor.name),
                _make_attack_card(actor.name),
                # 2 张基础防御（target_type=SELF：锁定自身、无需 targets；block 由牌本身承载）
                _make_defense_card(actor.name),
                _make_defense_card(actor.name),
                # 2 张自身向的恢复牌（均 target_type=SELF）：即时治疗 / 持续恢复，
                # 供 e2e 覆盖「SELF 无需 targets」的出牌通路
                _make_heal_card(
                    actor.name,
                    "急救敷药",
                    "一小包捣碎的止血草，混着几片发黄的旧布条。敷上伤口时疼得钻心，那股燥热的抽痛才一点点退下去，呼吸也跟着稳了些。",
                    heal=3,
                ),
                _make_regen_card(
                    actor.name,
                    "静息调匀",
                    "靠着墙根坐下来，把呼吸放慢，让胸口的起伏一点点平复。伤不会立刻就好，但每睡过一程，身子都比上一程更听使唤。",
                    heal=2,
                ),
            ],
        ),
        InventoryComponent(
            name=actor.name,
            items=[
                GearItem(
                    name="装备.旧铁剑",
                    description="一柄来历不明的旧铁剑，剑身有几处崩口，握柄缠着磨旧的皮绳。挥动时刃口带起一道沉闷的风声，像每一击都压着经年累月的力气；贴近剑格处锈迹斑斑，握在手里却比看上去更沉。",
                    speed=1,
                    cards=[_make_gear_offense_card()],
                ),
                GearItem(
                    name="装备.木盾",
                    description="一面用厚木板拼成的圆盾，边缘包着一圈铁皮，盾面刻着几道深浅不一的旧痕。举在身前时能把大半来势稳稳卸向一侧，木纹深处透着一股久经磕碰的韧劲。",
                    speed=-1,
                    cards=[_make_gear_defense_card()],
                ),
                ConsumableItem(
                    name="消耗品.灼血药剂",
                    description="一只粗陶小瓶，塞着软木塞，瓶里是暗绿的药液，闻着有草药的辛辣苦味。洒出时药液腾起一缕灼热的酸雾，蚀入皮肉。",
                    count=1,
                    cards=[
                        _make_consumable_card(
                            CONSUMABLE_SINGLE_SKELETON,
                            "消耗品.灼血药剂",
                            "小瓶抧出，暗绿的药液泼向对方，辛辣的酸雾随之腾起。",
                            damage=4,
                        )
                    ],
                ),
                ConsumableItem(
                    name="消耗品.爆裂卷轴",
                    description="一卷用麻布缠紧的羊皮卷，展开后是朱砂绘成的爆裂符文，边缘已熏得焦黑。掷出后会轰然炸开，碎片与热浪四溅。",
                    count=1,
                    cards=[
                        _make_consumable_card(
                            CONSUMABLE_AOE_SKELETON,
                            "消耗品.爆裂卷轴",
                            "麻布崩开，朱砂符文轰然炸响，碎片与热浪四向溅开。",
                            damage=2,
                        )
                    ],
                ),
            ],
        ),
    )

    return actor


#######################################################################################################################
def _iter_prompt_messages(blueprint: Blueprint) -> Iterator[Tuple[str, str]]:
    """遍历蓝图里所有实体的 (实体名, system_message)。"""
    for stage in blueprint.stages:
        yield stage.name, stage.system_message
        for actor in stage.actors:
            yield actor.name, actor.system_message
    for world in blueprint.world_entities:
        yield world.name, world.system_message


def _assert_no_dangling_world_refs(blueprint: Blueprint) -> None:
    """prompt 中出现的「世界.X」必须是蓝图里真实存在的世界实体。

    世界实体名只用于系统路由；写在故事层 prompt 里一旦改名不会有任何报错，
    prompt 只是悄悄指向一个不存在的实体。校验放在蓝图出厂处，setup 时直接失败。
    """
    known = {world.name for world in blueprint.world_entities}
    dangling = [
        f"{entity_name} → {ref}"
        for entity_name, message in _iter_prompt_messages(blueprint)
        for ref in _WORLD_ENTITY_REF_PATTERN.findall(message)
        if ref not in known
    ]
    assert (
        not dangling
    ), "prompt 引用了不存在的世界实体（改名后会静默失效）：" + "；".join(dangling)


def create_demo_blueprint(game_name: str) -> Blueprint:
    """创建演示游戏世界 Blueprint 实例：单人大厅 + 预置副本。"""

    lobby = create_lobby()

    blueprint = Blueprint(
        name=game_name,
        player_actor="角色.无名",
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=SYSTEM_RULES_FINAL,
        stages=[lobby],
        world_entities=[],
    )

    # 出厂闸门：prompt 里的悬空实体引用不放行
    _assert_no_dangling_world_refs(blueprint)

    return blueprint


###############################################################################################################################
# 消耗品世界实体已随「消耗品内置卡牌」重构移除：
# 消耗品现在物化为手牌后走静态出牌结算，不再需要独立的临时 agent。
###############################################################################################################################
