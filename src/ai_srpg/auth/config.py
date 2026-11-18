"""JWT 配置：签名密钥与有效期全部由环境变量提供。

做法与 ``pgsql/config.py`` 一致：导入即读取 ``.env``，缺变量立刻失败。区别是这里
不给默认密钥兜底——一个仓库里写死的 HS256 密钥等于没有签名，谁都能伪造令牌。
"""

import os
from typing import Final, final

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# 允许直接 ``import ai_srpg.auth`` 时就读取项目根目录的 .env，
# 不依赖调用方先执行 load_dotenv()。
load_dotenv()

#: 签名算法固定，不开放环境变量：配置一旦能改算法（如改成禁用校验的 none），
#: 安全性就取决于运维有没有填错，而不是取决于代码。
SIGNING_ALGORITHM: Final[str] = "HS256"

#: HS256 的密钥就是签名与校验的全部秘密，短密钥可被离线穷举。
MIN_SIGNING_KEY_LENGTH: Final[int] = 32


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise RuntimeError(
            f"缺少环境变量 {name}；请复制 .env.example 为 .env 并填入 JWT 配置"
        )
    return value


def _require_signing_key() -> str:
    key = _require_env("AI_SRPG_JWT_SIGNING_KEY")
    if len(key) < MIN_SIGNING_KEY_LENGTH:
        raise RuntimeError(
            f'环境变量 AI_SRPG_JWT_SIGNING_KEY 至少 {MIN_SIGNING_KEY_LENGTH} 个字符（当前 {len(key)}）；可用 python -c "import secrets; print(secrets.token_urlsafe(48))" 生成'
        )
    return key


def _require_positive_int(name: str) -> int:
    raw = _require_env(name)
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"环境变量 {name} 必须是整数: {raw!r}") from exc
    if value <= 0:
        raise RuntimeError(f"环境变量 {name} 必须是正整数: {raw!r}")
    return value


@final
class JWTConfig(BaseModel):
    """JWT 签发与校验配置（签名密钥、访问/刷新令牌有效期）。"""

    signing_key: str = Field(default_factory=_require_signing_key)
    refresh_token_expire_days: int = Field(
        default_factory=lambda: _require_positive_int(
            "AI_SRPG_JWT_REFRESH_TOKEN_EXPIRE_DAYS"
        )
    )
    access_token_expire_minutes: int = Field(
        default_factory=lambda: _require_positive_int(
            "AI_SRPG_JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
        )
    )


# 启动时校验并构建的配置实例；缺少任一必需变量会立即失败。
jwt_config: Final[JWTConfig] = JWTConfig()
