# SRPG AI 操作 CLI（ai-srpg-agent-game）

## 定位

`ai-srpg-agent-game` 是离线、快照驱动的副本推进入口：一次调用只完成一个动作，世界状态由快照承载，命令之间不保持进程内状态。它用于规则回归、问题复现与逐步观察 ECS 状态；需要走真实 HTTP 契约时改用 API 路径。

→ 参见：[SRPG AI 代理 API 走查 CLI（ai-srpg-agent-api）](run-agent-api.md)
→ 参见：[用户会话历史（PlayerSession）](session-history.md)

## 当前状态

命令面与参数已保留，动作层只有骨架：每条子命令初始化日志后把参数交给 `srpg_game_agent` 的动作函数，后者只记录调用，不读写世界状态、不推进游戏。待数据层与 SRPG 规则落地后填充实现。

## 命令面

顶层命令负责生命周期与观测：`new`、`stages`、`compact-context`、`enter-dungeon`、`next-dungeon`、`exit-dungeon`；房间动作按类型分组：`opening-init`；`combat-init`、`draw-cards`、`play-cards-specified`、`pass-turn`、`use-consumable`、`equip-gear`、`retreat`。

## 职责分层

Click 层只做参数解析、日志初始化与输出。动作编排在 `ai_srpg/srpg_game_agent/` 的 `core`、`dungeon`、`opening`、`combat`、`compact` 中；领域实现落地后，规则校验与 ECS 动作应放在可被服务端与测试复用的 services 层，CLI 只是薄壳。
