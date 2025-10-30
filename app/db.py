# app/db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Declarative Base for models
Base = declarative_base()

def detect_db_url():
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

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
