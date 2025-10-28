import os
import sys
from pathlib import Path
import ssl
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

# ✅ Ensure project root is in Python path
sys.path.append(str(Path(__file__).resolve().parents[1]))

# ✅ Load .env file
load_dotenv()

from app.db import Base
from app import models

config = context.config

# ✅ Choose DB URL based on mode
mode = os.getenv("MODE", "local")
database_url = os.getenv("DATABASE_URL")

if mode == "local" and (not database_url or "render.com" in database_url):
    # fallback for local development
    database_url = "sqlite:///./blockflow.db"
    print("⚙️ Using local SQLite database for Alembic migrations.")
else:
    print(f"🔗 Using PostgreSQL database ({'Render' if 'render.com' in database_url else 'Custom'})")

# ✅ Apply to Alembic
config.set_main_option("sqlalchemy.url", database_url)

# ✅ Logging setup
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    """Offline migrations (no DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Online migrations (connects to DB)."""
    connect_args = {}

    # 🧩 Render SSL Fix
    if "render.com" in database_url:
        connect_args = {"sslmode": "require", "sslrootcert": None}

    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
