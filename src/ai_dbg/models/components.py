"""ECS 组件定义。添加到实体后由对应系统读取处理。"""

from datetime import datetime
from typing import Dict, List, Optional, final

from pydantic import Field

from ..entitas.components import Component
from .artifact import Artifact
from .assets_meta import AssetKey
from .card import Card
from .character_stats import CharacterStats
from .combat import CombatResult, CombatState, CombatTurnStatus, RoundEntryKind
from .dungeon_room import DungeonRoomType
from .items import AnyItem, GearItem
from .registry import register_component_type


############################################################################################################
@final
@register_component_type
class IdentityComponent(Component):
    """为实体提供可读名称、创建顺序与全局唯一 ID。"""

    name: str
    creation_order: int  # 序列化时保证顺序一致性
    entity_id: str  # UUID 格式


############################################################################################################
@final
@register_component_type
class WorldComponent(Component):
    """标记实体为世界级实体（全局、唯一、独立于场景）。"""

    name: str


############################################################################################################
@final
@register_component_type
class StageComponent(Component):
    """标记实体为场景类型。"""

    name: str


############################################################################################################
@final
@register_component_type
class ActorComponent(Component):
    """标记实体为角色类型，记录当前所在场景。"""

    name: str
    current_stage: str  # 当前所在场景名称


############################################################################################################
@final
@register_component_type
class EnvironmentComponent(Component):
    """场景环境叙述，由 AI 根据当前状态动态生成，为行动规划与战斗初始化等系统提供背景信息。"""

    name: str
    narrative: str  # 叙述性描述文本


############################################################################################################
@final
@register_component_type
class PlayerComponent(Component):
    """标记角色由玩家控制（全局唯一）。"""

    player_name: str


############################################################################################################
@final
@register_component_type
class DestroyComponent(Component):
    """标记实体在下一帧销毁。"""

    name: str


############################################################################################################
@final
@register_component_type
class AppearanceComponent(Component):
    """存储角色外观描述；当前无时装系统，`appearance` 初始等于 `base_body`。"""

    name: str
    base_body: str  # 基础身体形态描述（不含装备）
    appearance: str  # 最终外观描述（含装备）


############################################################################################################
@final
@register_component_type
class LobbyComponent(Component):
    """标记场景为大厅/营地：两次副本之间的极简落脚点，不承载任何非副本玩法。"""

    name: str


############################################################################################################
@final
@register_component_type
class DungeonComponent(Component):
    """标记场景为副本类型。"""

    name: str


############################################################################################################
@final
@register_component_type
class DungeonRunComponent(Component):
    """一次副本运行的元数据，挂在副本实体上。"""

    name: str
    profile: str
    created_at: datetime
    assets: Dict[AssetKey, str] = Field(default_factory=dict)


############################################################################################################
@final
@register_component_type
class DungeonRoomComponent(Component):
    """副本房间元数据；当前与房间对应的 Stage 实体一一对应。"""

    name: str
    dungeon_name: str
    index: int
    room_type: DungeonRoomType


############################################################################################################
@final
@register_component_type
class CurrentDungeonRoomComponent(Component):
    """标记当前所在副本房间；同一时刻最多存在一个。"""

    name: str


############################################################################################################
@final
@register_component_type
class CombatComponent(Component):
    """标记战斗房间，并链接到该房间对应的战斗实体。"""

    name: str
    combat_name: str


############################################################################################################
@final
@register_component_type
class CombatStateComponent(Component):
    """战斗实体的状态机与结算信息。"""

    name: str
    room_name: str
    state: CombatState = CombatState.NONE
    result: CombatResult = CombatResult.NONE
    retreated: bool = False


############################################################################################################
@final
@register_component_type
class CombatRoundComponent(Component):
    """战斗回合实体上的回合生命周期状态。"""

    name: str
    combat_name: str
    index: int
    is_completed: bool = False
    draw_completed: bool = False


############################################################################################################
@final
@register_component_type
class CombatTurnComponent(Component):
    """回合内一个角色的行动槽；行动权、完成与死亡都落到单个槽上。"""

    name: str
    combat_name: str
    round_name: str
    actor_name: str
    order_index: int
    status: CombatTurnStatus = CombatTurnStatus.PENDING
    energy: int = 2


############################################################################################################
@final
@register_component_type
class CurrentCombatTurnComponent(Component):
    """标记战斗当前行动槽；同一战斗最多一个，回合结束时移除。"""

    name: str


############################################################################################################
@final
@register_component_type
class CombatRoundEntryComponent(Component):
    """回合内的一条操作记录；记录本身是独立实体，可被单独引用与查询。"""

    name: str
    combat_name: str
    round_name: str
    turn_name: Optional[str] = None
    index: int
    kind: RoundEntryKind
    log: str
    narrative: str


############################################################################################################
@final
@register_component_type
class CurrentCombatRoundComponent(Component):
    """标记战斗实体当前所在的回合；同一战斗最多一个。"""

    name: str


############################################################################################################
@final
@register_component_type
class NPCComponent(Component):
    """标记角色为 NPC（非玩家控制的友方角色），属于友方阵营。"""

    name: str


############################################################################################################
@final
@register_component_type
class PartyMemberComponent(Component):
    """标记角色为当前副本队伍活跃成员（NPCComponent 的子集，留守盟友不持有此组件）。"""

    name: str


############################################################################################################


@final
@register_component_type
class MonsterComponent(Component):
    """标记角色为怪物（敌方阵营战斗单位）。"""

    name: str


############################################################################################################
@final
@register_component_type
class HandComponent(Component):
    """存储角色当前手牌与所在回合数。"""

    name: str
    cards: List[Card]


############################################################################################################
@final
@register_component_type
class DeathComponent(Component):
    """标记角色已死亡，战斗系统排除此角色。"""

    name: str


############################################################################################################
############################################################################################################
@final
@register_component_type
class CharacterStatsComponent(Component):
    """存储角色战斗属性（HP、攻击力、防御力等）。"""

    name: str
    stats: CharacterStats


############################################################################################################
@final
@register_component_type
class MotifComponent(Component):
    """角色的艺术母题：为这个角色创造任何「作品」（卡牌、神器、称号……）时取用的取材锚点。

    ``motif`` 是一段合并的自由文本，覆盖四件事：
    - 母题：这一整套作品反复要讲的东西（一句话立意）；
    - 意象域：可反复取用的物件 / 质感 / 动作，必须场景中立（不得指向某个会消失的地点或在场者）；
    - 禁忌：不得出现的意象与语气；
    - 命名口吻：自称、称谓、句子长短。

    刻意与消费方解耦：组件只描述「这个人」，不绑定任何产物类型；卡牌专属的规则
    （词缀格式、牌组论题等）属于任务数据，不得写进这里。未挂该组件的角色，消费方
    应回退到「只用角色设定」的旧口径。
    """

    name: str
    motif: str  # 母题 + 意象域 + 禁忌 + 命名口吻（合并为一段）


############################################################################################################


@final
@register_component_type
class CardDesignComponent(Component):
    """标记世界实体为卡牌设计器（LLM 驱动）。

    统一承载「为某个 actor 选型 + 设计卡牌」的会话：调用方只传入目标 actor 的
    system prompt 与若干已物化候选卡，会话在临时上下文里跑完即丢，不在 actor 记忆留痕。
    """

    name: str


############################################################################################################
@final
@register_component_type
class ReliquaryComponent(Component):
    """神器容器组件：Actor/Stage 均可携带，承载该实体携带的神器列表。"""

    name: str
    artifacts: List[Artifact] = []


############################################################################################################


@final
@register_component_type
class DrawPileComponent(Component):
    """战斗内抽牌堆；Draw 阶段 FIFO 消耗，耗尽时自动将 DiscardPile 洗牌补入；存放 DeckComponent 原始牌的 model_copy() 副本，战斗结束后由 CombatPileTeardownSystem 清空。"""

    name: str
    cards: List[Card]  # FIFO 消耗，耗尽时由 DiscardPile 洗牌补充
    retained_cards: List[Card] = (
        []
    )  # retain 牌临时中转队列：回合末由 clear_round_state 写入，下回合 DrawCardsActionSystem 优先取回手牌（不占用抓牌名额）


############################################################################################################
@final
@register_component_type
class ExhaustPileComponent(Component):
    """消耗堆；存放主动弃置的自有牌副本，战斗内永久移出抽牌循环；战斗结束后由 CombatPileTeardownSystem 清空。"""

    name: str
    cards: List[Card]  # 按时间顺序追加，战斗内只增不减


############################################################################################################
@final
@register_component_type
class DiscardPileComponent(Component):
    """弃牌堆；出牌使用后或回合末剩余手牌进入此堆，DrawPile 耗尽时洗牌回补；存放副本，战斗结束后由 CombatPileTeardownSystem 清空。"""

    name: str
    cards: List[Card]  # 按时间顺序追加，DrawPile 耗尽时整体洗牌移入 DrawPile


############################################################################################################
@final
@register_component_type
class DeckComponent(Component):
    """跨战斗持久牌库。"""

    name: str
    cards: List[Card]


############################################################################################################
@final
@register_component_type
class SpoilsComponent(Component):
    """系统给予的奖励，内部以两个队列维护。

    - ``candidate_cards``：待领取候选卡队列（出队后移入 ``claimed_cards``）。
    - ``claimed_cards``：已领取卡队列（按领取顺序记录，供回看）。

    领取即从 ``candidate_cards`` 出队一张并追加进 ``claimed_cards``；组件保留作为“已生成”守卫。
    字段以奖励类型作前缀，未来可按需扩展 ``candidate_items`` / ``claimed_items`` 等。
    """

    name: str
    # 队列 A：待领取候选卡；领取后从本队列移除
    candidate_cards: List[Card]
    # 队列 B：已领取的卡（按领取顺序）
    claimed_cards: List[Card] = Field(default_factory=list)


############################################################################################################
@final
@register_component_type
class InventoryComponent(Component):
    """随身背包；存储角色当前携带的道具列表。"""

    name: str
    items: List[AnyItem]  # 当前携带的道具


############################################################################################################


@final
@register_component_type
class LootComponent(Component):
    """战斗战利品背包。"""

    name: str
    items: List[AnyItem]  # 本场战斗从怪物处获得的战利品（实践中为 MaterialItem）


############################################################################################################


@final
@register_component_type
class EquippedGearComponent(Component):
    """战斗中由当前行动者转化、待归还玩家背包的装备暂存列表；可同时存在于多个角色实体上。"""

    name: str
    items: List[GearItem]
