# 战斗管道（Combat Pipeline）

---

## 定位

战斗由全局 ECS 处理器链中的战斗段按注册顺序驱动：顺序即因果链，没有事件总线，也没有中心化状态机。战斗房间提供战场环境（stage）与参战角色（actors）；战斗本身是独立生命周期——初始化 → 多回合推进直到分出胜负 → 结束。

战斗、回合与行动槽的运行时状态都落在 ECS 实体上：战斗实体持有 `CombatStateComponent`，回合实体持有 `CombatRoundComponent`，每个角色的行动权落在独立的 `CombatTurnComponent` 实体上；房间实体只保留 `CombatComponent` 作为链接。API 与观测层读取的是由这些组件投影出的 `CombatView`，投影不落库、不参与状态推进。

---

## 三阶段框架

### 初始化（仅一次）

把预置牌库确定性填入抽牌堆，为参战角色挂载空牌堆并注入战场环境，随后切换到进行中。卡牌在此从 `DeckComponent` 进入 `DrawPileComponent`，尚未进手。

### 回合推进（循环，直到结果）

每回合内部是一条固定因果链：抽牌 → 出牌决策 → 动作执行 → 静态结算 → 死亡判定 → 回合完成 → 清理 → 胜负判定 → 下一回合。链由 `process()` 心跳驱动，各系统按注册顺序执行并自行判断是否适用；胜负判定是唯一退出分支。

抽牌是回合的唯一入口：`DrawCardsAction` 触发时先创建新回合（无回合或上一回合已完成时），再完成全员抽牌，二者在同一处理周期内连续完成。回合内行动均以抽牌完成为前置。

### 结束（仅一次）

掉落、战斗摘要归档、三堆牌副本清空、装备归还；`DeckComponent` 原始牌库完整保留。

---

## 回合与行动

`CombatRoundComponent` 只承载回合级生命周期：回合序号、是否完成、抽牌阶段是否完成。行动顺序与行动权由回合内的行动槽实体承载：

- `CombatTurnComponent`：每个参战角色在回合开始时生成一个行动槽，记录角色名、顺序序号、本回合剩余 energy 与状态（待行动 / 已完成 / 已死亡）。顺序按有效速度降序；有效速度 = 基础 `speed` + 已装备件 `speed` 之和。
- `CurrentCombatTurnComponent`：只标记当前行动槽，是行动权的唯一来源；同一战斗最多一个。
- `CombatPassSnapshotComponent`：动作阶段入口冻结当前行动槽，让决策与动作系统在同一次 pass 内共享同一个行动者。它不是行动权的来源，不注册、不参与快照持久化，并由 pipeline 的 cleanup 阶段兜底清除。

回合内的最小单位是**行动（turn）**：轮到某角色时，它可连续出牌、用消耗品、物化装备，直到它**过牌（pass turn）**。过牌只结束「这一个角色的行动窗口」；当且仅当所有存活角色都已过牌，回合才完成。能量耗尽只限制能打出的牌数，不自动过牌。`CombatRoundView` 仍以 `action_order`、`completed_actors`、`current_actor` 暴露投影。

---

## 出牌结算

出牌结算由所在场景执行，但不再调用 LLM。系统只使用卡牌字段与目标当前状态做确定性计算：

- 每个目标先取 `hits`：`SINGLE` / `ALL` / `SELF` 使用 `hit_count`；`SPREAD` 的解析目标列表就是命中分配，`hits` 为该目标在列表中的出现次数。
- 每击伤害 = `max(0, damage − 目标手牌总格挡)`，再乘以 `hits`；目标 HP clamp 到 `0 ~ max_hp`。
- `block` 仍是持有期属性：出牌不给攻击者追加格挡，也不消耗目标格挡。
- 伤害只写 HP；死亡由后续 `DeathSystem` 处理，胜负由 `CombatOutcomeSystem` 判定。

结算结果通过 `CombatArbitrationEvent` 广播给场景内其他角色，并只对实际 HP 变化的目标写 `stats_update` 通知。战斗日志由系统按同一段计算生成，过程与结果天然同源；`narrative` 使用卡牌 `description` 或静态行动描述，不再由 LLM 生成。

---

## 词缀数据边界

`on_play_affixes` / `on_hit_affixes` / `on_turn_end_affixes` / `on_autonomous_affixes` / `engine_affixes` 仍是 `Card` 的数据字段，保留给展示与未来的静态规则引擎。

当前战斗结算**不消费**这些字段：受击、回合结束、自主运行与牌堆运转不会因词缀文本触发；系统也不会解释词缀、选择倍率或执行反伤 / 吸血 / 治疗。词缀文本目前是预留数据，不是既成战斗力。

模型层没有独立的状态 / buff 组件：一个角色当前的「状态」仍由其手牌承载，尤其是手牌 `block` 之和构成的总格挡。`transferable` 仍按确定性规则投递副本，但副本携带的词缀不产生额外结算。

→ 参见：[卡牌数据模型（Card）](card.md)、[手牌（HandComponent）](hand.md)、[消耗品系统（ConsumableItem）](consumable-item.md)

---

## 决策与结算分离

出牌分决策与结算两步：决策由各行动者并行完成，结算单线程执行。怪物决策由 `MonsterCombatDecisionSystem` 使用角色自身记忆与工具循环完成；队员侧由外部玩家决定，系统只记录同形决策。结算不再有 LLM 参与，因此决策阶段的模型选择不会改变结算口径。

怪物决策的对手视图只暴露 `HP`、总格挡与手牌总数，并按需点亮与当前决策相关的牌；内容快照通过 `read_piles` 工具按需读取，不常驻上下文。

→ 参见：[工具即上下文（Tools as Context）](tools-as-context.md)

---

## 记忆与失败

出牌结算只广播事实与 HP 变化，不再为场景实体写 LLM 总结。角色侧记忆仍区分「决策」与「容器事实」：决策记录做了什么与原因，牌堆变更记录只写给容器主人。事实的权威载体始终是组件，记忆负责让人知道发生过什么。

任何系统内部错误都会中止当前 job 并记录 `job_failed`，随后从最近快照恢复 `DBGGame`；结算本身不再有「未提交 / 未落库」的软失败分支。

→ 参见：[Job 执行与事件日志（Job Execution）](job-execution.md)、[世界快照持久化（World Persistence）](world-persistence.md)

---

## 跨系统关系

- 预置副本文件提供房间定义（stage + actors + 预置卡牌）；运行时房间落到对应场景实体上 → 参见：[DBG AI 操作 CLI（ai-dbg-agent-game）](run-agent-game.md)
- 装备系统将装备物化为临时手牌参与出牌，与普通卡牌共用静态结算 → 参见：[装备系统（GearItem）](gear-item.md)
- 消耗品系统将内置卡牌物化为手牌，与普通卡牌共用静态结算 → 参见：[消耗品系统（ConsumableItem）](consumable-item.md)
