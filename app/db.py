import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# ==========================================================
# 🧠 DATABASE CONFIGURATION
# ==========================================================

# Use DATABASE_URL from Render if available, otherwise local SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

# Render’s Postgres URLs sometimes start with 'postgres://'
# SQLAlchemy requires 'postgresql://'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# ==========================================================
# ⚙️ ENGINE & SESSION
# ==========================================================
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# ==========================================================
# 🔁 DATABASE SESSION DEPENDENCY
# ==========================================================
def get_db():
    """
    Dependency for FastAPI routes.
    Creates a new database session for each request and
    ensures it is closed when the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================================
# 🧱 OPTIONAL: INIT DB (for local testing)
# ==========================================================
def init_db():
    """
    Create all tables defined in SQLAlchemy models.
    Run this manually if tables don’t auto-create.
    """
    from app import models  # import your models here
    Base.metadata.create_all(bind=engine)
