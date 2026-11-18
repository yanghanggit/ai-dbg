"""卡牌与状态效果模型定义。"""

from typing import Final, Tuple, final
from uuid import uuid4

from loguru import logger
from pydantic import BaseModel, Field, model_validator

from .str_list import NormalizedStrList
from .target_type import TargetType


###############################################################################################################################################
@final
class Card(BaseModel):
    """战斗卡牌"""

    name: str
    description: str  # 叙事锚点：不含数值，不重述其它字段已确定的效果
    on_play_affixes: NormalizedStrList = (
        []
    )  # 即时词缀（多值，预留数据）：每个元素是一条完整独立词缀，格式 `[词缀名]:机械结算描述`；当前战斗结算不消费；无则 []
    on_hit_affixes: NormalizedStrList = (
        []
    )  # 受击词缀（多值，预留数据）：当前战斗结算不消费；无则 []
    on_turn_end_affixes: NormalizedStrList = (
        []
    )  # 回合结束词缀（多值，预留数据）：当前战斗结算不消费；无则 []
    on_autonomous_affixes: NormalizedStrList = (
        []
    )  # 自主运行词缀（多值，预留数据）：当前战斗结算不消费；无则 []
    engine_affixes: NormalizedStrList = (
        []
    )  # 运转词缀（多值，预留数据）：当前战斗结算不消费；类别由槽位本身决定，词缀名照常写风味名；无则 []
    playable: bool = True  # 是否可出牌；False 时系统阻止出牌操作
    exhaust: bool = False  # 出牌后永久归入 ExhaustPile，不进入 DiscardPile 循环
    retain: bool = (
        False  # 回合末保留在手牌（不进入 DiscardPile），跨回合留在 HandComponent
    )
    ethereal: bool = False  # pass turn 时若仍留在手牌，自动移入 ExhaustPileComponent
    transferable: bool = (
        False  # 出牌时按命中分配额外投递副本（副本 uuid 重新生成、transferable 置 False，不可再次传递；本体照常结算并进入弃牌/消耗流程）；副本数 = 该角色在解析目标列表中的出现次数：SPREAD 一击一份（只剩一个目标时全摊在它身上），SINGLE/ALL/SELF 各一份
    )
    cost: int = 1  # 出牌费用；消耗当前 energy；不足时禁止出牌
    damage: int = 0  # 单次伤害
    hit_count: int = 1  # 攻击次数；>1 时为多段攻击，每段独立结算
    block: int = 0  # 手牌持有期间提供的格挡；结算时计入持有者总格挡
    target_type: TargetType = (
        TargetType.SINGLE
    )  # 目标类型，决定目标约束策略；SELF 锁定出牌者本人且无需 targets
    source: str = ""  # 卡牌来源（生成/注入者）名称；空字符串表示来源未知
    uuid: str = Field(default_factory=lambda: str(uuid4()))  # 全局唯一标识符

    @model_validator(mode="after")
    def _reject_multiline_affixes(self) -> "Card":
        """一条词缀必须是单行：多值列表用「多个元素」表达多条规则，不是用换行塞进一个元素。"""
        for field in AFFIX_FIELDS:
            for affix in getattr(self, field):
                assert (
                    "\n" not in affix
                ), f"Card「{self.name}」的 {field} 里有换行：一条词缀只写一行的单条规则，多条规则请拆成多个列表元素"
        return self

    @model_validator(mode="after")
    def _warn_flag_conflicts(self) -> "Card":
        """报警（不拦截）：检测布尔标志的互斥/死组合，仅记录告警日志。"""
        if self.retain and self.ethereal:
            logger.warning(
                f"Card「{self.name}」同时开启 retain 与 ethereal：二者互斥，pass turn 时 ethereal 会先于回合末 retain 生效，retain 永不触发。"
            )
        if self.ethereal and self.on_autonomous_affixes:
            logger.warning(
                f"Card「{self.name}」同时开启 ethereal 与 on_autonomous_affixes：ethereal 会在自主运行阶段之前把牌移入 ExhaustPile，自主词缀永不触发。"
            )
        if not self.playable and self.transferable:
            logger.warning(
                f"Card「{self.name}」playable=false 但 transferable=true：牌不可出，transferable 永不触发，属无效组合。"
            )
        if not self.playable and self.exhaust:
            logger.warning(
                f"Card「{self.name}」playable=false 但 exhaust=true：牌不可出，exhaust 永不触发，属无效组合。"
            )
        if not self.playable and self.engine_affixes:
            logger.warning(
                f"Card「{self.name}」playable=false 但带运转词缀：牌不可出，运转词缀永不触发，属无效组合。"
            )
        return self


###############################################################################################################################################


#######################################################################################################################################
AFFIX_FIELDS: Final[Tuple[str, ...]] = (
    "on_play_affixes",
    "on_hit_affixes",
    "on_turn_end_affixes",
    "on_autonomous_affixes",
    "engine_affixes",
)
