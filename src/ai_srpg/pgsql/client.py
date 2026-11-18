from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import sessionmaker

from .base import Base
from .config import postgresql_config

############################################################################################################

# Create a SQLAlchemy engine using the PostgreSQL connection string from the configuration
engine = create_engine(postgresql_config.connection_string)

# 创建一个新的会话工厂，用于生成数据库会话
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


############################################################################################################
def pgsql_database_exists(database_name: str) -> bool:
    """
    判断数据库是否存在
    """

    # 构建连接到 postgres 数据库的连接字符串
    postgres_conn_str = postgresql_config.admin_connection_string

    try:

        # 连接到 postgres 数据库
        postgres_engine = create_engine(postgres_conn_str)

        # 查询 pg_database 系统表以检查数据库是否存在
        with postgres_engine.connect() as conn:

            # 使用参数化查询以防止SQL注入
            result = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": database_name},
            )

            # 检查查询结果是否为空，如果不为空，则数据库存在
            exists = result.fetchone() is not None

        # 关闭连接
        postgres_engine.dispose()
        return exists

    except Exception as e:
        logger.error(f"❌ 检查数据库是否存在时出错: {e}")
        raise


############################################################################################################
def pgsql_create_database(database_name: str) -> None:
    """
    创建数据库
    """

    # 先检查数据库是否已存在
    if pgsql_database_exists(database_name):
        logger.info(f"✅ 数据库 {database_name} 已存在，跳过创建")
        return

    # 构建连接到 postgres 数据库的连接字符串
    postgres_conn_str = postgresql_config.admin_connection_string

    try:

        # 连接到 postgres 数据库
        postgres_engine = create_engine(
            postgres_conn_str,
            isolation_level="AUTOCOMMIT",  # CREATE DATABASE 需要 AUTOCOMMIT 模式
        )

        # 使用 with 语句确保连接在使用后被正确关闭
        with postgres_engine.connect() as conn:

            # 创建数据库
            conn.execute(text(f'CREATE DATABASE "{database_name}"'))
            logger.success(f"✅ 数据库 {database_name} 创建成功")

        # 关闭连接
        postgres_engine.dispose()

    except Exception as e:
        logger.error(f"❌ 创建数据库失败: {e}")
        raise


############################################################################################################
def pgsql_drop_database(database_name: str) -> None:
    """
    删除数据库
    注意：此操作不可逆，仅适用于开发环境
    """

    # 先检查数据库是否存在
    if not pgsql_database_exists(database_name):
        logger.info(f"ℹ️ 数据库 {database_name} 不存在，无需删除")
        return

    # 构建连接到 postgres 数据库的连接字符串
    postgres_conn_str = postgresql_config.admin_connection_string

    try:

        # 连接到 postgres 数据库
        postgres_engine = create_engine(
            postgres_conn_str,
            isolation_level="AUTOCOMMIT",  # DROP DATABASE 需要 AUTOCOMMIT 模式
        )

        with postgres_engine.connect() as conn:
            # 强制断开所有连接到目标数据库的会话
            conn.execute(
                text(
                    f"""
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE pg_stat_activity.datname = :dbname
                    AND pid <> pg_backend_pid()
                    """
                ),
                {"dbname": database_name},
            )

            # 删除数据库
            conn.execute(text(f'DROP DATABASE "{database_name}"'))
            logger.warning(f"🗑️ 数据库 {database_name} 已删除")

        # 关闭连接
        postgres_engine.dispose()

    except Exception as e:
        logger.error(f"❌ 删除数据库失败: {e}")
        raise


############################################################################################################
def _upgrade_job_event_payload(conn: Connection) -> None:
    """把 ``job_events.payload`` 从 ``text`` 升级为 ``jsonb``（幂等）。

    ``Base.metadata.create_all`` 只建缺失的表，不会修改已存在列的类型；旧库在这里
    补一次，升级后直接对 JSON 内部字段做 SQL 查询。
    """
    current = conn.execute(
        text(
            """
            SELECT data_type FROM information_schema.columns
            WHERE table_name = 'job_events' AND column_name = 'payload'
            """
        )
    ).scalar()
    if current is None or current == "jsonb":
        return

    sql = "ALTER TABLE job_events ALTER COLUMN payload TYPE jsonb USING payload::jsonb"
    conn.execute(text(sql))
    logger.info(f"✅ job_events.payload 类型已从 {current} 升级为 jsonb")


############################################################################################################
def pgsql_ensure_database_tables() -> None:
    """
    确保数据库表已创建
    这个函数在需要时才会被调用，避免导入时立即连接数据库
    """
    try:

        # 先确保 pgvector 扩展已启用
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            logger.info("✅ pgvector 扩展已确保启用")

        # 导入模型注册模块以确保所有模型被注册到Base.metadata中
        from .model_registry import register_all_models

        # 调用注册函数以确保所有模型都被注册
        register_all_models()

        # 确保所有表都已创建
        Base.metadata.create_all(bind=engine)
        logger.info("✅ 数据库表结构已确保存在")

        # 历史库的列类型升级（create_all 不会改已存在的列）
        with engine.begin() as conn:
            _upgrade_job_event_payload(conn)

    except Exception as e:
        logger.error(f"❌ 创建数据库表时出错: {e}")
        raise


############################################################################################################
