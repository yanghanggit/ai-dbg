"""PostgreSQL 连接配置：全部字段来自环境变量。"""

import os
from typing import Final, final

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from sqlalchemy.engine import URL

# 允许直接 ``import ai_srpg.pgsql`` 时就读取项目根目录的 .env，
# 不依赖调用方先执行 load_dotenv()。
load_dotenv()


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@final
class PostgreSQLConfig(BaseModel):
    host: str = Field(default_factory=lambda: _env("AI_SRPG_DB_HOST", "localhost"))
    port: int = Field(default_factory=lambda: int(_env("AI_SRPG_DB_PORT", "5432")))
    database: str = Field(default_factory=lambda: _env("AI_SRPG_DB_NAME", "ai-srpg-db"))
    user: str = Field(default_factory=lambda: _env("AI_SRPG_DB_USER", "postgres"))
    password: str = Field(default_factory=lambda: _env("AI_SRPG_DB_PASSWORD", ""))

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


# 默认配置实例
postgresql_config: Final[PostgreSQLConfig] = PostgreSQLConfig()
