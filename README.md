# AI-SRPG

一个基于**多智能体架构**与 **ECS (Entity Component System)** 的 AI 驱动型 SRPG（Strategy RPG）框架：
以 ECS 承载可重建的世界状态与快照，以 LLM（DeepSeek）驱动叙事生成；玩法规则与 LLM 决策待重建。

> 本仓库是**引擎 + 常驻服务端 + 服务端真相**，自带一个面向 AI 代理的命令行工具与 LLM 调用留痕。

## 🛠️ 技术栈

- **Python 3.12+** / **FastAPI** / **Pydantic v2**
- **DeepSeek**（chat + reasoner）
- **PostgreSQL**（pgvector 为基建，当前业务未调用）
- **Sentence Transformers** / **Replicate**（嵌入与文生图基建，当前业务未调用）
- **uv** / **Black** / **Ruff** / **MyPy** / **Pytest**

## 🚀 快速开始

### 环境要求

- Python 3.12+
- PostgreSQL
- [uv](https://github.com/astral-sh/uv)

### 安装

```bash
git clone <repository-url>
cd ai-srpg

make install        # 等价 uv sync（含 dev 依赖组）
# 或
uv sync

source .venv/bin/activate        # macOS/Linux
# .\.venv\Scripts\activate       # Windows
```

### 配置

复制 `cp .env.example .env`，填好数据库连接、`DEEPSEEK_API_KEY`、`GAME_SERVER_PORT` 等。

### 初始化测试数据库

```bash
uv run python -m scripts.seed_db     # 种子蓝图写入 .blueprints/，并重建空库（表结构 + Procrastinate + 测试用户）
```

> 会删除目标库中的全部数据，运行前请确认 `.env` 指向的是开发库。

## ▶️ 启动与使用

### 启动游戏服务器

```bash
uv run ai-srpg-server                  # --port 缺省读 .env 的 GAME_SERVER_PORT
uv run ai-srpg-server --host 0.0.0.0 --port 8000

# 验证
curl http://127.0.0.1:8000/
```

生产环境用 PM2 托管：

```bash
pm2 start ecosystem.config.js
```

### 后台定时任务

服务器在 `lifespan` 内启动两个进程内定时循环（与 `GameServer` 同进程 / 同事件循环）：

| 环境变量 | 默认 | 说明 |
| --- | --- | --- |
| `GAME_ROOM_REAP_INTERVAL_SECONDS` | `60` | 空闲房间回收的扫描间隔 |
| `GAME_ROOM_TTL_SECONDS` | `1800` | 房间空闲多久后被回收；`<=0` 关闭回收 |
| `GAME_TICK_INTERVAL_SECONDS` | `60` | 游戏玩法定时器（`services/gameplay_scheduler.py`）的间隔；`<=0` 关闭 |

游戏玩法定时器目前仅为骨架（`on_room_tick` 为空实现），用于后续添加“定时查看 ECS 状态并触发玩法”的逻辑。

### 面向 AI 代理的工具（非人工操作）

游戏的「操作」由 AI 代理驱动，日常无需人手动执行。此处仅列入口，
**用法、参数与环境变量见对应文档**：

| 命令 | 用途 | 文档 |
| --- | --- | --- |
| `ai-srpg-agent-game` | 离线、快照驱动推进（动作骨架；含 LLM 调用观测） | [docs/wiki/run-agent-game.md](docs/wiki/run-agent-game.md) |

`uv run <命令> --help` 可列出全部子命令。

## 🔧 开发

```bash
make install        # uv sync（含 dev 依赖组）+ editable 安装
make test           # uv run pytest tests/ -v
make lint           # uv run mypy --strict + ruff check
make format         # black 格式化
```

### 测试约定

- 测试一律 `from ai_srpg... import ...`（**不要** `from src.ai_srpg...`）——测试、脚本、生产共用同一导入身份。
- `tests/` 不是包（无 `__init__.py`）；pytest 走 `--import-mode=importlib` + `pythonpath=["src"]`。
- 共享测试代码放包里（如 `src/ai_srpg/entitas/testing.py`）或 `tests/conftest.py` 的 fixture，不要 `from tests... import`。

> **Windows 用户**：需装 [Git Bash](https://git-scm.com/) 与 Make（`winget install ezwinports.make`）。

## 📚 文档

架构文档位于 `docs/`，以 [docs/README.md](docs/README.md) 为根节点。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

[许可证信息]
