"""JWT 配置全部来自环境变量；令牌有效期取自配置而非写死。"""

from datetime import datetime, timezone
from typing import Any, Dict

import pytest

from ai_srpg.auth.config import MIN_SIGNING_KEY_LENGTH, JWTConfig, jwt_config
from ai_srpg.auth.jwt import create_access_token, create_refresh_token, decode_jwt_token

_KEY = "k" * MIN_SIGNING_KEY_LENGTH


###############################################################################
def test_config_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_SRPG_JWT_SIGNING_KEY", _KEY)
    monkeypatch.setenv("AI_SRPG_JWT_REFRESH_TOKEN_EXPIRE_DAYS", "3")
    monkeypatch.setenv("AI_SRPG_JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "12")

    config = JWTConfig()

    assert config.signing_key == _KEY
    assert config.refresh_token_expire_days == 3
    assert config.access_token_expire_minutes == 12


def test_requires_signing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_SRPG_JWT_SIGNING_KEY", raising=False)

    with pytest.raises(RuntimeError, match="AI_SRPG_JWT_SIGNING_KEY"):
        JWTConfig()


def test_rejects_short_signing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_SRPG_JWT_SIGNING_KEY", "too-short")

    with pytest.raises(RuntimeError, match="至少 32 个字符"):
        JWTConfig()


def test_requires_positive_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_SRPG_JWT_SIGNING_KEY", _KEY)
    monkeypatch.setenv("AI_SRPG_JWT_REFRESH_TOKEN_EXPIRE_DAYS", "0")
    monkeypatch.setenv("AI_SRPG_JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")

    with pytest.raises(RuntimeError, match="AI_SRPG_JWT_REFRESH_TOKEN_EXPIRE_DAYS"):
        JWTConfig()


def test_rejects_non_integer_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_SRPG_JWT_SIGNING_KEY", _KEY)
    monkeypatch.setenv("AI_SRPG_JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")
    monkeypatch.setenv("AI_SRPG_JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "half")

    with pytest.raises(RuntimeError, match="必须是整数"):
        JWTConfig()


###############################################################################
def _ttl_seconds(payload: Dict[str, Any]) -> float:
    return float(payload["exp"]) - datetime.now(timezone.utc).timestamp()


def test_access_token_uses_configured_ttl() -> None:
    token = create_access_token({"sub": "user-1"})
    payload = decode_jwt_token(token)

    assert payload["sub"] == "user-1"
    assert payload["jti"]
    expected = jwt_config.access_token_expire_minutes * 60
    assert abs(_ttl_seconds(payload) - expected) < 5


def test_refresh_token_uses_configured_ttl() -> None:
    token = create_refresh_token({"sub": "user-1"})
    payload = decode_jwt_token(token)

    expected = jwt_config.refresh_token_expire_days * 24 * 60 * 60
    assert abs(_ttl_seconds(payload) - expected) < 5


def test_custom_expires_delta_wins() -> None:
    from datetime import timedelta

    token = create_access_token({"sub": "user-1"}, expires_delta=timedelta(minutes=1))
    payload = decode_jwt_token(token)

    assert abs(_ttl_seconds(payload) - 60) < 5
