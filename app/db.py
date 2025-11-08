# app/db.py
import os
import warnings
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import OperationalError

# Suppress Neon quota spam
warnings.filterwarnings("ignore", message=".*data transfer quota.*")

Base = declarative_base()


def detect_db_url():
    """Detect DATABASE_URL or fallback SQLite path."""
    env = os.getenv("DATABASE_URL")
    if env:
        return env

    candidates = [
        "sqlite:///./blockflow_v5.db",
        "sqlite:///./app/blockflow_v5.db",
        "sqlite:///../blockflow_v5.db",
        "sqlite:///./blockflow.db",
    ]
    for c in candidates:
        if c.startswith("sqlite:///"):
            f = c.replace("sqlite:///", "")
            if os.path.exists(f):
                return c
    return candidates[0]


DATABASE_URL = detect_db_url()


def create_engine_with_fallback():
    """Try NeonDB first; fallback to SQLite automatically if failed."""
    try:
        engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False}
            if DATABASE_URL.startswith("sqlite")
            else {},
            pool_pre_ping=True,
        )
        # Test connection (SQLAlchemy 2.x needs text())
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"[OK] Connected to primary database: {DATABASE_URL}")
        return engine
    except OperationalError as e:
        print(
            f"[WARN] Primary DB connection failed ({str(e)}). "
            "Switching to local fallback SQLite DB..."
        )
        fallback_url = "sqlite:///./demo_fallback.db"
        fallback_engine = create_engine(
            fallback_url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )
        return fallback_engine


engine = create_engine_with_fallback()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency that yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ----------------------------------------------------------------------
# Auto-create schema in fallback mode (ensures tables exist locally)
# ----------------------------------------------------------------------
try:
    from app import models  # noqa
    Base.metadata.create_all(bind=engine)
    print("[INIT] Created missing tables in fallback DB (if not existing).")
except Exception as e:
    print(f"[WARN] Could not auto-create tables: {e}")
