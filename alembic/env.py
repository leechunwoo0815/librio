# alembic/env.py
"""
[What] Alembic迁移环境配置
[Why] 让Alembic知道如何连接数据库和找到模型
[How] 导入模型元数据，配置连接
"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from backend.database import Base

# 导入所有模型，确保它们被注册到Base.metadata
from backend.models import User, Child

config = context.config

# 尝试从环境变量获取数据库URL，如果不存在则使用alembic.ini中的配置
import os
if os.environ.get("DATABASE_URL"):
    config.set_main_option("sqlalchemy.url", os.environ.get("DATABASE_URL"))
elif not config.get_main_option("sqlalchemy.url") or config.get_main_option("sqlalchemy.url") == "None":
    from backend.config import get_settings
    settings = get_settings()
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
