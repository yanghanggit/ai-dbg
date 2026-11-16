# 消耗品系统（ConsumableItem）

---

## 定位

消耗品是战斗中可主动使用的**队伍级**道具，库存由 player 持有（团队背包），使用动作挂在当前行动的我方角色上。

使用**不消耗 energy、不推进回合**：消耗品本身固定 **0 费**，使用时只是把内置卡牌**物化为手牌**；真正结算效果的是之后打出的那张牌。

消耗品与装备（`GearItem`）**同构**：蓝图阶段固化内置卡牌（`cards`），战斗中物化为手牌、走普通出牌逻辑。区别只有两点：

- **一次性**：消耗品卡固定 `exhaust=True`，打出后进 `ExhaustPile`，不像装备那样在战斗结束时归还；
- **用后即扣**：物化时立刻从队伍背包扣减库存，装备则是「用后归还」。

→ 参见：[装备系统（GearItem）](gear-item.md)（同为队伍级道具，物化为手牌）

---

## 内置卡牌（cards）

`ConsumableItem` 携带 `cards: List[Card]`，与 `GearItem.cards` 同名同语义——它是**一份**消耗品携带的内置牌（一般仅一张）：

- 蓝图阶段即固化为完整 `Card` 规格，战斗使用不再调用 LLM；
- 卡牌固定 **`cost=0`** 且 **`exhaust=True`**，由 `ConsumableItem` 的模型校验**强制**；
- 当前消耗品**只做伤害**：效果由 `Card.damage`（配 `hit_count` / `target_type`）承载，不走治疗、格挡或状态。

物化数量 = **每个内置牌 × `count`**：一次使用会消耗整条库存（其全部 `count`），每张内置牌各生成 `count` 份手牌副本。

---

## 战斗使用管道

**物化阶段**（`UseConsumableItemActionSystem`）：先从团队背包（player 的 `InventoryComponent`）**按 uuid 移除整条消耗品**（消耗其全部 `count`）；扣库存成功后才把 `cards` 物化为手牌——每个内置牌 × count 生成对应份数的独立副本（重生成 `uuid`、`source` 记为发起行动者、强制 `retain=True`）。随后向场景内所有存活角色广播使用通知，并追加一条 `RoundEntryKind.CONSUMABLE` 回合记录实体。

**结算阶段**（`PlayCardsArbitrationSystem`）：物化出的牌与任何普通手牌一样，由出牌仲裁结算伤害，结果追加一条 `RoundEntryKind.CARDS` 回合记录实体。

> 为什么物化出的牌要强制 `retain=True`：回合末 `clear_round_state` 会把非 retain 手牌塞进弃牌堆，而 DrawPile 耗尽时弃牌堆会被洗回 DrawPile。若不 retain，一张本回合没用掉的消耗品卡会在后续回合被重新抽到并再次打出，而库存早已扣了 1 份——等于一份消耗品重复生效。`retain` 让它在手牌中留到打出为止，战斗结束由 `CombatPileTeardownSystem` 清掉副本。
>
> 消耗品卡**不叠加角色属性**：`Card.damage` 就是最终伤害（与装备刻意不同——装备物化时会叠加持有者的 `attack` / `defense`）。

---

## 来源

当前版本没有工坊合成；消耗品来自蓝图里的初始背包。`resources` 与堆叠规则保留为后续生产/掉落系统的扩展位，当前不参与战斗逻辑。

→ 参见：[卡牌数据模型（Card）](card.md)
