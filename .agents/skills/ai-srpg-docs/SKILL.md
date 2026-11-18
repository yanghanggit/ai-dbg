---
name: ai-srpg-docs
description: Write or revise ai-srpg documentation under docs/ following the repository's normative writing constraints. Use when editing docs/, adding wiki pages, compressing existing docs, or documenting CLI behavior.
---

# ai-srpg 文档写作

开始任何 `docs/` 下的写作前，先完整阅读仓库根目录的 [docs/README.md](../../../docs/README.md)。其中的「写作约束（AI 编写文档时必须遵守）」是规范来源，本技能只负责路由与执行提醒；两者冲突时以 `docs/README.md` 为准。

写作时执行以下检查：

- 写设计意图、架构决策与跨系统关联，不写实现步骤、文件清单或代码已能自述的细节。
- 只引用相对稳定的标识（核心类名、命令名、协议字段）；避免复述易变的函数名、变量名与内部字段。
- 保持紧凑：逐段自问「删掉后设计意图是否仍完整」，能删则删。
- 只写系统层面，不写表现层；每篇聚焦一个系统，跨系统对比用交叉引用而非横向对比表。
- 禁止代码块；命令、路径、标识用行内代码。
- 交叉引用统一写作 `→ 参见：[文档标题](相对路径)`，放在段落末或独立行。
- 写 CLI 文档前先核对 `src/ai_srpg/cli/` 中的实际命令与参数，避免文档落后于代码。
- 新增文档后立即更新 `docs/README.md` 的索引。
