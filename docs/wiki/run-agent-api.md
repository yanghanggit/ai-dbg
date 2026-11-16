# DBG AI 代理 API 走查 CLI（ai-dbg-agent-api）

---

## 定位

`ai-dbg-agent-api` 是 AI 代理对常驻服务端做 HTTP 走查的入口：一次调用只完成一次动作，世界状态只存在于服务端。它既是接口契约的探针，也是代理在真实运行态上观察、试探与纠错的工具；不承担本地游戏推进。

服务端是唯一真相，CLI 不缓存世界状态、不读写 `.worlds/`，只以 `--user/--game` 寻址。每次动作前用 `status` 取当前局面；`login` 会清除该 user 已有房间，只应在开新局时调用一次。

→ 参见：[DBG AI 操作 CLI（ai-dbg-agent-game）](run-agent-game.md)
→ 参见：[世界快照持久化（World Persistence）](world-persistence.md)

## 交互契约

- **单一 JSON 封套**：成功返回动作结果；失败返回错误详情并以非零退出码结束。服务端 HTTP 4xx/5xx 的 `detail` 原样透出，代理据此自我纠错。
- **异步任务自动等待**：服务端返回任务 ID 的动作，CLI 通过 SSE 等到终态再输出，代理无需轮询。
- **stdout 只放 JSON**：运行日志写 stderr 与文件，控制台级别由 `AI_DBG_API_LOG_LEVEL` 控制，避免污染代理输出。
- **身份无状态**：只按 `--user/--game` 寻址，不落盘对局状态；同一身份可在多条命令间复用服务端内存中的房间。

命令面按动作域分组：顶层 `login` / `logout` / `new-game` / `status` / `blueprint-list` / `dungeon-list` / `compact`，以及 `home`、`dungeon`、`opening`、`spoils`、`combat`。命令是服务端 API 的薄映射，参数与校验以服务端为准。

## 观测与流程推断

`status` 是走查的核心：它把跨接口取数收拢为一次只读快照，覆盖当前模式（家园/副本）、场景与角色、属性/手牌、副本房间与开场奖励、战斗状态与最近回合、家园队伍/背包/储物箱、会话消息；`--actor` 可显式指定玩家角色，`--messages-since` 只拉增量消息。

快照同时附带 `suggested_actions`，沉淀的是流程推进知识，而非固定脚本：

- **家园**：`home advance` / `home speak` / `home switch-stage` / `home generate-dungeon` / `home enter-dungeon` / `home roster-add` / `home roster-remove` / `home item-to-inventory` / `home item-to-storage` / `home craft-consumable` / `home craft-gear` / `home craft-costume` / `home wear-costume` / `home remove-costume` / `compact`。
- **开场房间**：未初始化 → `opening init`；未生成奖励 → `spoils generate`；已生成 → 逐角色 `spoils pick-card`，随后 `dungeon advance-stage`；`spoils remove` 用于复位，`dungeon exit` 离开。
- **战斗房间**：`NONE` / `INITIALIZATION` → `combat init`；`ONGOING` 未抓牌或回合已结束 → `combat draw-cards`；轮到角色 → `combat play-cards` / `combat pass-turn` / `combat use-consumable` / `combat equip-gear`（怪物回合由服务端决策），也可 `combat retreat`；`COMPLETE` / `POST_COMBAT` 胜利 → `combat collect-loot`，有下一关再 `dungeon advance-stage`；其余结束态 → `dungeon exit`。

建议字符串已带命令组前缀，可直接作为 CLI 参数；它只是提示，最终以服务端校验为准。

## 连接层

连接配置集中在 `ServerConfig`：host/port、`http`/`https`、TLS 校验与 JWT 都由 CLI 参数或 `AI_DBG_API_*` 环境变量注入；自签证书可关闭校验或传 CA bundle。当前鉴权是静态 Bearer token；将来若改为登录换 token、401 自动刷新，只需改连接层，命令面与代理协议不变。

## 与回归测试的分工

代理走查依赖 LLM 判断，不可复现，不能替代固定回归：接口契约与回归由集成测试固定，代理负责探索、新特性走查与边界试探。
