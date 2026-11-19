#!/usr/bin/env python3
"""开发数据库重置脚本：把库重置到可直接开始测试的初始状态。

这是破坏性的完整重置，不是增量 seed：会删除目标库后重建。

步骤：
1. 重建蓝图产物（``.blueprints/`` 与 ``logs/blueprints/``，内容见 ``seeds/``）；
2. 删除并重建 ``postgresql_config.database`` 指定的数据库；
3. 建业务表（含 pgvector 扩展）；
4. 建 Procrastinate 任务队列表结构；
5. 写入开发测试用户。

用法：

    uv run python -m scripts.reset_dev_db

注意：会**删除**目标库中的全部数据，运行前请确认 ``.env`` 指向的是开发库。
"""

import asyncio
from typing import Final, final

from loguru import logger
from pydantic import BaseModel

from ai_srpg.pgsql import (
    pgsql_create_database,
    pgsql_drop_database,
    pgsql_ensure_database_tables,
    postgresql_config,
    procrastinate_app,
)
from ai_srpg.pgsql.user_operations import has_user, save_user
from scripts.build_blueprint import build_blueprint_artifacts

###########################################################################################################
###########################################################################################################
###########################################################################################################


@final
class UserAccount(BaseModel):
    """初始化时写入的开发测试账号。"""

    user_name: str
    hashed_password: str
    display_name: str


#: 本次重建用的内容源与游戏名
SOURCE: Final[str] = "dark_fantasy/nameless_camp"
GAME_NAME: Final[str] = "Game1"

TEST_USER: Final[UserAccount] = UserAccount(
    user_name="yanghangethan@gmail.com",
    hashed_password="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # 明文是 secret
    display_name="yh",
)


###########################################################################################################
def _seed_blueprint() -> None:
    """重建蓝图产物（蓝图 JSON 与提示词留痕）。"""
    logger.info(f"🗺️ 重建蓝图产物: source={SOURCE}, game={GAME_NAME}")
    path = build_blueprint_artifacts(SOURCE, GAME_NAME)
    logger.success(f"✅ 蓝图已写入 {path}")


###########################################################################################################
async def _apply_procrastinate_schema() -> None:
    """创建 Procrastinate 任务队列所需的表结构。"""
    async with procrastinate_app.open_async():
        await procrastinate_app.schema_manager.apply_schema_async()


###########################################################################################################
def _seed_user() -> None:
    """检查并创建测试用户账号。"""
    logger.info("👤 检查测试用户...")
    if has_user(TEST_USER.user_name):
        logger.info(f"测试用户 {TEST_USER.user_name} 已存在，跳过")
        return
    save_user(
        user_name=TEST_USER.user_name,
        hashed_password=TEST_USER.hashed_password,
        display_name=TEST_USER.display_name,
    )
    logger.success(f"✅ 测试用户 {TEST_USER.user_name} 已创建")


###########################################################################################################
def main() -> None:
    """执行完整的数据库初始化流程。"""
    logger.info(f"🚀 重置开发数据库: {postgresql_config.database}")

    _seed_blueprint()

    logger.info("🗑️ 删除旧数据库（如果存在）...")
    pgsql_drop_database(postgresql_config.database)

    logger.info("📦 创建新数据库...")
    pgsql_create_database(postgresql_config.database)

    logger.info("📋 创建数据库表结构（含 pgvector 扩展）...")
    pgsql_ensure_database_tables()

    logger.info("🧱 创建 Procrastinate 任务队列表结构...")
    asyncio.run(_apply_procrastinate_schema())

    _seed_user()

    logger.success(f"🎉 数据库 {postgresql_config.database} 已就绪")


###########################################################################################################
if __name__ == "__main__":
    main()
