# Job 执行与事件日志（Job Execution）

`Job` 是一次可由服务端异步执行的业务动作，使用 Procrastinate 的 job id 作为唯一标识。Procrastinate 只管排队与执行状态；执行过程由 `job_events` 记录。两者合起来构成客户端的 job 视图。

## 设计意图

- **job 是执行单元，不是领域历史**：一次动作对应一个 job；它回答「这次执行走到哪、哪个 system 失败」，不承载玩家可见的完整叙事。
- **队列状态不复制**：job 的排队/执行/终态仍以 Procrastinate 为准，不另建一套状态枚举或状态表。
- **过程可观察**：pipeline 在每个 system 边界写入开始、结束、耗时与失败事件；失败时不用等终态就能定位到具体 system。
- **失败可定位**：系统异常立即停止后续 system；job 标记失败并保留完整失败事件。
- **会话不回滚**：用户会话历史独立于 job，失败尝试仍保留在上帝视角中，以 `job_id` 与 job 结果关联。

## 执行链路

动作接口只负责派发并返回 job id。worker 执行 job 时依次：

1. 绑定当前 job 上下文；
2. 记录 job 开始；
3. 进入玩家房间事务，把后续领域事件关联到该 job；
4. 推动唯一全局 pipeline；pipeline 观测器逐 system 写入开始/结束/失败；
5. 成功后记录 job 成功；
6. 失败时记录 system 失败并记录 job 失败。

失败不重建游戏实例，job 事件记录到具体 system 为止。

## 与客户端

- 批量状态查询只返回精简 job 状态。
- 单个 job 查询返回状态与完整事件。
- 事件接口支持按事件 id 增量读取，适合长任务轮询。
- SSE 监听在终态结束；取消与中止也视为终态，不会被当作永久运行。
- job 事件中的失败摘要面向客户端，完整异常栈留在服务端日志。

→ 参见：[用户会话历史（PlayerSession）](session-history.md)
→ 参见：[SRPG AI 代理 API 走查 CLI（ai-srpg-agent-api）](run-agent-api.md)
