import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# ✅ Load environment variables from .env file
load_dotenv()

# ✅ Get PostgreSQL URL from .env
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL not found in environment variables!")

# ✅ Create the SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# ✅ Create a session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ✅ Base class for all models
Base = declarative_base()
