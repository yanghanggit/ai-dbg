# AI-DBG 知识库根节点

> 这是 `docs/` 目录的唯一入口。每次新增文档领域时，请在此处更新索引。
> Agent 从此处出发，可定位到任何知识。
>
> **写作约束（AI 编写文档时必须遵守）**
>
> **写什么**
>
> - 写**设计意图与架构决策**：解释"为何这样设计"、"与哪些系统交互"，不描述实现步骤。代码已能自述的细节不再复述。
> - 写**跨系统关联**：本系统如何被其他系统驱动、产出被谁消费。单系统内部的步骤逻辑靠代码阅读。
> - 写**相对稳定的知识**：核心类名（如 `GearItem`、`DeckComponent`）可用行内代码引用；变量名、函数名、字段名随实现变化，引用它们等于复述代码，应规避。
> - 写**紧凑精要**：追求信息密度，避免铺陈。一段文字如果删掉后设计意图仍然完整，就该删。
> - 写**系统层面而非表现层**：只陈述引擎与系统的事实和关系，不写表现层的呈现、交互或实现归属。
>
> **怎么写**
>
> - 禁止代码块（` ``` `）。
> - 交叉引用格式：`→ 参见：[文档标题](相对路径)`，置于段落末或独立行。
> - 每篇聚焦一个系统；跨系统对比用交叉引用表达，不在同文档内做横向对比表。
> - 结论优先，比喻克制：先给结论性质的事实，再给支撑它的关系；过程性描述只做必要因果交代，比喻只在能一语点破时使用、不铺陈。
>
> **何时新建文档**
>
> - 新增文档的条件：出现了一个独立的设计概念，其意图和关联无法用现有文档的一两段话说清。
> - 否则更新已有文档。新建后立即更新本页索引。

---

## 知识领域索引

### wiki/ — 核心系统设计

| 文档 | 简介 |
| ------ | ------ |
| [消耗品系统（ConsumableItem）](wiki/consumable-item.md) | 消耗品的数据模型、内置卡牌与战斗使用管道 |
| [装备系统（GearItem）](wiki/gear-item.md) | 装备的数据模型、装备物化为手牌的管道、战斗结束归还 |
| [材料系统（MaterialItem）](wiki/material-item.md) | 战斗掉落材料的数据模型、堆叠规则与当前无消费端的定位 |
| [DBG AI 操作 CLI（ai-dbg-agent-game）](wiki/run-agent-game.md) | 离线快照驱动的副本推进：新局直达副本、开场/战斗/奖励流程、管道骨架与开发调测命令 |
| [DBG AI 代理 API 走查 CLI（ai-dbg-agent-api）](wiki/run-agent-api.md) | 一次调用一次动作、服务端为唯一真相；status 快照与 suggested_actions 驱动代理走查 |
| [世界快照持久化（World Persistence）](wiki/world-persistence.md) | 开发期明文快照留痕的设计意图：人可读状态切片、快照驱动 CLI 的读写循环、非最终存储的定位 |
| [战斗管道（Combat Pipeline）](wiki/combat-pipeline.md) | ECS 处理器链的架构设计：管道心跳驱动、牌库预置与抽牌堆确定性填充、仲裁的三方归属、回合行动序列与生命周期阶段 |
| [神器（Artifact）](wiki/artifact.md) | 第一公民实体：内容作者写修正规则，由 `ReliquaryComponent` 声明归属，运行点由标记组件表达，出牌仲裁后由神器自身实体作为临时 agent 自行判定并执行，机制与内容分离 |
| [卡牌数据模型（Card）](wiki/card.md) | Card 字段的三层结构（确定性骨架 / 语义词缀 / 生命周期流转）、来源引用（source）与「确定性骨架 + LLM 语义」的设计取舍 |
| [卡牌设计指南（Card Design）](wiki/card-design.md) | 面向内容作者的设计方法论：设计总原则、布尔字段硬约束、字段设计含义、词缀设计方法（字段/词缀/范例均指向各自单一来源） |
| [三端化思维（攻击端 / 防御端 / 运转端）](wiki/combat-ports.md) | 端口化思维方法论：攻击端（前端/成长性/铺垫）、防御端（前端/成长性/特殊）、运转端（过牌/加费/启动）及其与 Card 字段的映射 |
| [工具即上下文（Tools as Context）](wiki/tools-as-context.md) | 方法论：工具的 name/description/parameters 本身即上下文；据此把约束下沉到 schema / description / 对象说明，减少提示词重复与冗余 |
| [手牌（HandComponent）](wiki/hand.md) | 手牌的双重身份：作为出牌者的行动选择集、作为被命中者的当前状态，及其与牌堆/仲裁/装备的关联 |
| [DBG 核心概念定义与逻辑关系总结](<wiki/DBG 核心概念定义与逻辑关系总结.md>) | Modifiers（对局级规则）与 Affixes（一次性效果词缀）二者的定义、归属与逻辑关系：宏观-微观模型 |
| [上下文窗口管理（Context Window Management）](wiki/context-window-management.md) | 应对 agent 记忆膨胀的两种减量手段（精简提示词、阈值触发压缩）；以及仅作用于地下城场景实体的仲裁 loop 逐次压缩与失败不回滚策略 |
| [角色自持内容生成（Actor Intrinsic Generation）](wiki/actor-intrinsic-generation.md) | 以角色/怪物为 agent 生成候选卡与牌库时的取材边界：只取内化身份，排除当前场景等易变外部信息 |
| [战役设定与全局规则（CAMPAIGN_SETTING / SYSTEM_RULES）](wiki/campaign-setting-rules-bridge.md) | 故事层两字段的分层（均封存在 demo/）、抽象设定的惰性知识与内容无关边界 |
