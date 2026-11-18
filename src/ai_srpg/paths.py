"""全局路径常量。

项目内所有目录在此统一定义，导入即创建目录（mkdir + assert）。
注意：所有路径均为相对路径，要求从项目根目录运行。
"""

from pathlib import Path

###########################################################################################################################################
# 游戏蓝图目录（scripts/reset_dev_db.py 写入）
BLUEPRINTS_DIR: Path = Path(".blueprints")
BLUEPRINTS_DIR.mkdir(parents=True, exist_ok=True)
assert BLUEPRINTS_DIR.exists(), f"找不到目录: {BLUEPRINTS_DIR}"

###########################################################################################################################################
# 资源资产目录（raw 资源 + 同名 .meta；assets_meta / 静态文件服务使用）
ASSETS_DIR: Path = Path(".assets/image")
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
assert ASSETS_DIR.exists(), f"找不到目录: {ASSETS_DIR}"

###########################################################################################################################################
# LLM 调用记录目录（llm/call_records.py 追加 JSONL；开发期查问题 / 调提示词）
LLM_CALLS_DIR: Path = Path(".llm_calls")
LLM_CALLS_DIR.mkdir(parents=True, exist_ok=True)
assert LLM_CALLS_DIR.exists(), f"找不到目录: {LLM_CALLS_DIR}"

###########################################################################################################################################
# 日志文件目录（各 CLI 入口写运行日志）
LOGS_DIR: Path = Path("logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
assert LOGS_DIR.exists(), f"找不到目录: {LOGS_DIR}"

###########################################################################################################################################
# 蓝图 prompt 留痕目录（构建蓝图时按实体导出 system prompt，便于逐段核对提示词）
PROMPTS_DIR: Path = LOGS_DIR / "blueprints"
PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
assert PROMPTS_DIR.exists(), f"找不到目录: {PROMPTS_DIR}"
