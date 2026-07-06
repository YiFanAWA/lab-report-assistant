"""Alembic 环境配置。"""

from logging.config import fileConfig
from sqlalchemy import pool
from alembic import context

from app.core.config import settings
from app.infrastructure.database.engine import Base
from app.modules.projects.models import Project  # noqa: F401
from app.modules.requirements.models import RequirementSource, RequirementPlan, ChangeRecord  # noqa: F401
from app.modules.sources.models import Source, ParsedDocument, EvidenceCard  # noqa: F401
from app.modules.jobs.models import BackgroundJob  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    from sqlalchemy import create_engine
    connectable = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
