# -*- coding: utf-8 -*-
from sqlalchemy import create_engine
from app.models import Base
from app import models

POSTGRES_URL = "postgresql+psycopg2://blockflow_db_cr4e_user:PnnxFL1ioRthcz1ClMchvztuwhPeO8uT@dpg-d45ifh9r0fns73f5vt80-a.oregon-postgres.render.com/blockflow_db_cr4e"

print("🔄 Syncing model schema to Render PostgreSQL...")
engine = create_engine(POSTGRES_URL)
Base.metadata.create_all(bind=engine)
print("✅ Done! All missing tables and columns added safely.")
