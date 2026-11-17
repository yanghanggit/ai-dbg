"""游戏动作组件。添加到实体后由对应系统处理执行。"""

from typing import List, final

from ..entitas.components import Component
from .card import Card
from .items import ConsumableItem
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
    """发起使用团队背包内指定装备的意图。

    action 只携带原始意图（装备名）；当前行动者、手牌、背包与装备实例
    全部由 ``EquipGearItemActionSystem`` 解析和校验。
    """

    name: str
    item_name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class ExitDungeonAction(Component):
    """发起退出当前副本、返回大厅的意图；具体校验与传送由 ExitDungeonActionSystem 执行。"""

    name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class TeardownDungeonAction(Component):
    """退出副本成功后，请求销毁副本相关实体；由 TeardownDungeonActionSystem 响应。"""

    name: str


############################################################################################################
@final
@register_action_component_type
@register_component_type
class FillDrawPileAction(Component):
    """触发从 DeckComponent 洗牌填充 DrawPileComponent，由 FillDrawPileSystem 响应处理。"""

    name: str
