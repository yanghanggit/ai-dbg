# SRPG AI 操作 CLI（ai-srpg-agent-game）

## 定位

`ai-srpg-agent-game` 是离线、快照驱动的游戏开发辅助入口：一次调用只完成一个动作，世界状态由快照承载，命令之间不保持进程内状态。它用于规则回归、问题复现与逐步观察 ECS 状态；需要走真实 HTTP 契约时改用 API 路径。

→ 参见：[用户会话历史（PlayerSession）](session-history.md)

## 当前状态

游戏动作类命令的命令面与参数已保留，动作层只有骨架：每条子命令初始化日志后把参数交给 `srpg_game_agent` 的动作函数，后者只记录调用，不读写世界状态、不推进游戏。待数据层与 SRPG 规则落地后填充实现。

LLM 调用观测命令已经可用，不属于骨架：它们读取结构化调用记录，用于排查请求、对比提示词与检查失败原因。

## 命令面

顶层命令负责生命周期与观测：`new`、`stages`、`compact-context`。读取状态的命令用 `--user` / `--game` 定位对局，`--snapshot-id` 可指定历史快照，缺省使用最新。

调用观测命令：`llm-calls` 按时间倒序列出最近调用，可按标签、用户、游戏、命令、agent loop、轮次、`cli`/`room` 作用域与时间范围过滤，也可输出 JSON 供脚本分析；`llm-call` 按完整 id 或唯一前缀展开一次调用，包含系统提示、历史消息、AI 回复、工具调用、推理过程、错误信息与调用来源。

记录随调用附带分析维度：用户、游戏、命令、快照标识、job 标识、agent loop 与轮次、agent/entity 名称，以及调用开始时间与上下文占比。文件按作用域切分：CLI 每次进程独立目录，服务端按房间独立目录；`make clean-llm-calls` 可整体清空，不做保留策略。

## 职责分层

Click 层只做参数解析、日志初始化与输出。动作编排在 `ai_srpg/srpg_game_agent/` 的 `core` 与 `compact` 中；领域实现落地后，规则校验与 ECS 动作应放在可被服务端与测试复用的 services 层，CLI 只是薄壳。

→ 参见：[Job 执行与事件日志（Job Execution）](job-execution.md)
