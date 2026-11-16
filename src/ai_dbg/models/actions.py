"""游戏动作组件。添加到实体后由对应系统处理执行。"""

from enum import StrEnum, unique
from typing import List, Optional, final

from ..entitas.components import Component
from .card import Card
from .items import ConsumableItem, GearItem
from .registry import register_action_component_type, register_component_type

############################################################################################################


@final
@register_action_component_type
@register_component_type
class CompactContextAction(Component):
    """触发对指定 agent 的记忆进行手动上下文压缩。

    动作挂载在被压缩实体自身，name 即该实体名；由
    CompactContextActionSystem 响应 ADDED 事件执行压缩。
    """

    name: str


############################################################################################################


@final
@register_action_component_type
@register_component_type
class DrawCardsAction(Component):
    """触发角色在战斗回合中抽取卡牌。"""

    name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class PlayCardsAction(Component):
    """触发角色使用手牌对目标释放技能。"""

    name: str
    card: Card  # 使用的卡牌
    targets: List[str]  # 技能目标角色名列表


############################################################################################################
@final
@register_action_component_type
@register_component_type
class PassTurnAction(Component):
    """触发角色主动跳过本次出牌机会，消耗 1 点 energy，推进行动顺序。"""

    name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class RetreatAction(Component):
    """触发角色从战斗中撤退。"""

    name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class MonsterTurnAction(Component):
    """标记当前轮到指定怪物行动，触发 MonsterCombatDecisionSystem 进行出牌决策。"""

    name: str


############################################################################################################


@final
@register_action_component_type
@register_component_type
class UseConsumableItemAction(Component):
    """触发当前行动者使用队伍背包内的消耗品：扣减库存并把其内置卡牌物化进手牌。"""

    name: str
    item: ConsumableItem  # 使用的消耗品对象（从队伍背包 InventoryComponent 检索后填入）


############################################################################################################
@final
@register_action_component_type
@register_component_type
class EquipGearItemAction(Component):
    """触发当前行动者（我方）将团队背包内的装备转化为手牌。"""

    name: str
    item: GearItem  # 使用的装备对象（从 InventoryComponent 检索后填入）


############################################################################################################
@final
@register_action_component_type
@register_component_type
class GenerateSpoilsAction(Component):
    """触发为角色生成候选奖励（SpoilsComponent），当前生成候选卡牌。

    ``prototype_ids`` 为外部入口的**显式候选规格**（调测 / 脚本用）：非空时
    ``GenerateSpoilsActionSystem`` 只物化这些原型（顺序、重复均照给），不再随机抽取。
    空列表 = 默认随机抽取，与旧行为完全一致。

    动作组件由 ``ActionCleanupSystem`` 每帧清理，不随着存档持久化，仅用于本次传递。
    """

    name: str
    prototype_ids: List[str] = []  # 显式指定的原型 id（可重复；空 = 随机抽取）


############################################################################################################
@final
@unique
class SpoilRewardKind(StrEnum):
    """Spoils 奖励类型；用于区分 PickSpoilsAction 的领取子操作。"""

    CARD = "card"  # 卡牌（当前唯一实现；未来可扩展 ITEM / ARTIFACT）


############################################################################################################
@final
@register_action_component_type
@register_component_type
class PickSpoilsAction(Component):
    """触发角色从 SpoilsComponent 领取一项奖励（umbrella）。

    当前仅实现卡牌子操作（reward_kind=CARD），由 activate_pick_spoils_card
    检索后填入 card；未来可扩展 item / artifact 等子操作。
    """

    name: str
    reward_kind: SpoilRewardKind = SpoilRewardKind.CARD  # 领取的奖励类型
    card: Optional[Card] = None  # reward_kind == CARD 时有效


############################################################################################################
@final
@register_action_component_type
@register_component_type
class FillDrawPileAction(Component):
    """触发从 DeckComponent 洗牌填充 DrawPileComponent，由 FillDrawPileSystem 响应处理。"""

    name: str
