"""PostgreSQL 连接配置全部来自环境变量。"""

import pytest
from sqlalchemy.engine import make_url

from ai_srpg.pgsql.config import PostgreSQLConfig

_ENV_NAMES = (
    "AI_SRPG_DB_HOST",
    "AI_SRPG_DB_PORT",
    "AI_SRPG_DB_NAME",
    "AI_SRPG_DB_USER",
    "AI_SRPG_DB_PASSWORD",
)


def test_postgresql_config_reads_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_SRPG_DB_HOST", "db.example")
    monkeypatch.setenv("AI_SRPG_DB_PORT", "6543")
    monkeypatch.setenv("AI_SRPG_DB_NAME", "game-db")
    monkeypatch.setenv("AI_SRPG_DB_USER", "alice")
    monkeypatch.setenv("AI_SRPG_DB_PASSWORD", "p@ss word")

    config = PostgreSQLConfig()
    url = make_url(config.connection_string)

    assert url.host == "db.example"
    assert url.port == 6543
    assert url.database == "game-db"
    assert url.username == "alice"
    assert url.password == "p@ss word"
    assert make_url(config.admin_connection_string).database == "postgres"


def test_postgresql_config_requires_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(RuntimeError, match="AI_SRPG_DB_HOST"):
        PostgreSQLConfig()


def test_postgresql_config_allows_empty_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_SRPG_DB_HOST", "localhost")
    monkeypatch.setenv("AI_SRPG_DB_PORT", "5432")
    monkeypatch.setenv("AI_SRPG_DB_NAME", "game-db")
    monkeypatch.setenv("AI_SRPG_DB_USER", "alice")
    monkeypatch.setenv("AI_SRPG_DB_PASSWORD", "")

    assert PostgreSQLConfig().password == ""
