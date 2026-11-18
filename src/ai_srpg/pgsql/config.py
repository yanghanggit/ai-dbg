"""PostgreSQL 连接配置：所有字段必须由环境变量提供。"""

import os
from typing import Final, final

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from sqlalchemy.engine import URL

# 允许直接 ``import ai_srpg.pgsql`` 时就读取项目根目录的 .env，
# 不依赖调用方先执行 load_dotenv()。
load_dotenv()


def _require_env(name: str, *, allow_empty: bool = False) -> str:
    value = os.getenv(name)
    if value is None or (not allow_empty and value.strip() == ""):
        raise RuntimeError(
            f"缺少环境变量 {name}；请复制 .env.example 为 .env 并填写 PostgreSQL 配置"
        )
    return value


def _require_port() -> int:
    raw = _require_env("AI_SRPG_DB_PORT")
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"环境变量 AI_SRPG_DB_PORT 必须是整数: {raw!r}") from exc


@final
class PostgreSQLConfig(BaseModel):
    host: str = Field(default_factory=lambda: _require_env("AI_SRPG_DB_HOST"))
    port: int = Field(default_factory=_require_port)
    database: str = Field(default_factory=lambda: _require_env("AI_SRPG_DB_NAME"))
    user: str = Field(default_factory=lambda: _require_env("AI_SRPG_DB_USER"))
    password: str = Field(
        default_factory=lambda: _require_env("AI_SRPG_DB_PASSWORD", allow_empty=True)
    )

    def _url(self, *, database: str) -> str:
        return URL.create(
            "postgresql",
            username=self.user,
            password=self.password or None,
            host=self.host,
            port=self.port,
            database=database,
        ).render_as_string(hide_password=False)

    @property
    def connection_string(self) -> str:
        return self._url(database=self.database)

    @property
    def admin_connection_string(self) -> str:
        """连接到 ``postgres`` 库，用于创建 / 删除目标数据库。"""
        return self._url(database="postgres")


# 启动时校验并构建的配置实例；缺少任一必需变量会立即失败。
postgresql_config: Final[PostgreSQLConfig] = PostgreSQLConfig()
