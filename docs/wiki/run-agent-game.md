# DBG AI 操作 CLI（ai-dbg-agent-game）

---

## 定位

`ai-dbg-agent-game` 是离线、快照驱动的副本推进工具：一次调用只完成一个动作，世界状态不在进程内，而在 `.worlds/{user}/{game}/{timestamp}/`。每条命令都执行同一循环：读取快照 → `restore_game` → 触发动作 → 对应管道推进 → 写出新快照。命令之间没有持久内存，任意一份快照都可独立复位并继续。

它不依赖常驻服务端，适合复现问题、做规则回归和逐步观察 ECS 状态。需要走真实 HTTP 契约时改用 API 路径。

→ 参见：[DBG AI 代理 API 走查 CLI（ai-dbg-agent-api）](run-agent-api.md)
→ 参见：[世界快照持久化（World Persistence）](world-persistence.md)

## 运行模型

新局由 `new` 直接进入副本首间，不再经过非副本场景。副本结束后 `exit-dungeon` 把角色送回极简大厅 `场景.营地`；大厅没有社交、合成、队伍或储物玩法，只作为下一次 `enter-dungeon` 的入口。

副本内部按房间类型推进：开场房间执行 `opening-init`、生成并领取奖励；战斗房间执行 `combat-init`、抽牌与回合循环。`next-dungeon` 只推进房间，不初始化新房间；初始化始终由代理显式选择 `opening-init` 或 `combat-init`。

## 命令面

顶层命令负责生命周期与观测：`new`、`stages`、`enter-dungeon`、`exit-dungeon`、`next-dungeon`、`compact-context`。副本动作按房间类型分组：`opening-init`、`generate-spoils`、`pick-card`、`remove-spoils`；`combat-init`、`draw-cards`、`play-cards-specified`、`pass-turn`、`use-consumable`、`equip-gear`、`retreat`、`collect-loot`。卡牌调测命令 `card-prototypes`、`design-cards`、`rebuild-deck` 只读或只改副本文件，不写对局状态。

## 职责分层

Click 层只做参数解析、日志初始化、快照路径构造与错误退出。动作编排在 `ai_dbg/dbg_game_agent/`：`core.py` 负责创建/复位游戏，`dungeon.py` 负责进入、推进、退出，`opening.py` 与 `spoils.py` 负责开场与奖励，`combat.py` 负责战斗动作，`compact.py` 负责记忆压缩，`cards.py` 负责卡牌调测。

真正的规则校验与 ECS 动作触发在 `ai_dbg/services/`。这一层与 CLI 解耦，同时被服务端 API 与测试复用；CLI 不是规则实现处，只是快照读写与动作选择的薄壳。

## 管道骨架

每份快照恢复后，游戏实例会重新创建所有管道；动作入口只调用与当前房间匹配的那一条。开场与战斗共享同一副骨架：`PrologueSystem`、`EnvironmentInitializationSystem`、`ActionCleanupSystem`、`DestroyEntitySystem`、`ContextCompactionSystem`、`EpilogueSystem`。中间段才是模式差异：开场插入角色开场初始化、奖励生成与领取；战斗插入牌堆初始化、回合开始/抽牌、怪物与队伍决策、出牌与仲裁、死亡判定、回合清理、胜负判定、掉落与牌堆拆除。

顺序就是因果链：回合开始必须先于抽牌，死亡判定必须先于胜负判定，胜负判定必须先于掉落，后战斗转换必须先于牌堆拆除。工厂函数中的相邻注释是对这些不可交换顺序的显式约束。

→ 参见：[战斗管道（Combat Pipeline）](combat-pipeline.md)

## 与测试的分工

CLI 的端到端走查依赖 LLM，结果不可完全复现，不能替代固定回归。规则与契约由单元/集成测试锁定；CLI 用于探索新副本、验证卡牌设计与观察完整快照差异。卡牌开发循环使用 `card-prototypes` 查原型、`design-cards` 预览设计、`rebuild-deck` 定点改写预置副本的怪物牌库。

→ 参见：[卡牌设计指南（Card Design）](card-design.md)
