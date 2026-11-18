# SRPG AI 操作 CLI（ai-srpg-agent-game）

---

## 定位

`ai-srpg-agent-game` 是离线、快照驱动的副本推进工具：一次调用只完成一个动作，世界状态不在进程内，而在 `.worlds/{user}/{game}/{timestamp}/`；用户级会话历史独立存放在 `.sessions/`，跨快照持续累积。每条命令都执行同一循环：读取世界快照并加载用户会话 → `restore_game` → 触发动作 → 唯一全局 pipeline 推进 → 写出新快照。命令之间没有持久内存，任意一份世界快照都可独立复位并继续。

它不依赖常驻服务端，适合复现问题、做规则回归和逐步观察 ECS 状态。需要走真实 HTTP 契约时改用 API 路径。

→ 参见：[SRPG AI 代理 API 走查 CLI（ai-srpg-agent-api）](run-agent-api.md)
→ 参见：[世界快照持久化（World Persistence）](world-persistence.md)
→ 参见：[用户会话历史（PlayerSession）](session-history.md)

## 运行模型

新局由 `new` 直接进入副本首间，不再经过非副本场景。副本结束后 `exit-dungeon` 把角色送回极简大厅 `场景.营地`；大厅没有社交、合成、或储物玩法，只作为下一次 `enter-dungeon` 的入口。

副本内部按房间类型推进：开场房间执行 `opening-init`；战斗房间执行 `combat-init`、抽牌与回合循环。`next-dungeon` 只推进房间，不初始化新房间；初始化始终由代理显式选择 `opening-init` 或 `combat-init`。

## 命令面

顶层命令负责生命周期与观测：`new`、`stages`、`enter-dungeon`、`exit-dungeon`、`next-dungeon`、`compact-context`。副本动作按房间类型分组：`opening-init`；`combat-init`、`draw-cards`、`play-cards-specified`、`pass-turn`、`use-consumable`、`equip-gear`、`retreat`。当前命令面不包含卡牌创建或牌库重做玩法。

## 职责分层

Click 层只做参数解析、日志初始化、快照路径构造与错误退出。动作编排在 `ai_srpg/srpg_game_agent/`：`core.py` 负责创建/复位游戏，`dungeon.py` 负责进入、推进、退出，`opening.py` 负责开场，`combat.py` 负责战斗动作，`compact.py` 负责记忆压缩。

真正的规则校验与 ECS 动作触发在 `ai_srpg/services/`。这一层与 CLI 解耦，同时被服务端 API 与测试复用；CLI 不是规则实现处，只是快照读写与动作选择的薄壳。

## 全局 system 骨架

每份快照恢复后，游戏实例只创建一条全局 pipeline。动作入口只负责把动作挂到实体上并推动这条 pipeline，不再按开场/战斗/压缩选择执行序列。全局 schedule 固定，所有 system 每轮按注册顺序执行，由 system 自己检查房间状态、战斗状态或动作组件是否适用。

开场、战斗是 `world` 中的房间状态，压缩是 `CompactContextAction` 动作；三者都不是独立的 pipeline。开场 system 在战斗回合中自行跳过，战斗 system 在开场或压缩回合中同样自行跳过。

顺序就是因果链：回合开始必须先于抽牌，死亡判定必须先于胜负判定，胜负判定必须先于战后转换，后战斗转换必须先于牌堆拆除。全局装配函数中的相邻注释是对这些不可交换顺序的显式约束。

→ 参见：[战斗管道（Combat Pipeline）](combat-pipeline.md)

## 与测试的分工

CLI 的端到端走查依赖 LLM，结果不可完全复现，不能替代固定回归。规则与契约由单元/集成测试锁定；CLI 用于探索新副本与观察完整快照差异。
