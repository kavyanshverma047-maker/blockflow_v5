from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, scoped_session
DATABASE_URL = 'sqlite:///./blockflow_v5.db'
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))
Base = declarative_base()
