import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Fetch DATABASE_URL from .env or Render environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./blockflow.db")

# Connection args for SQLite only
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# Create engine
engine = create_engine(DATABASE_URL, connect_args=connect_args)

# Session & Base setup
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency for DB sessions
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
