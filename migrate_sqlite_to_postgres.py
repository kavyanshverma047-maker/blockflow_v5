# -*- coding: utf-8 -*-
import pandas as pd
from sqlalchemy import create_engine, inspect
from tqdm import tqdm
import math

SQLITE_PATH = "blockflow.db"
POSTGRES_URL = "postgresql+psycopg2://blockflow_db_cr4e_user:PnnxFL1ioRthcz1ClMchvztuwhPeO8uT@dpg-d45ifh9r0fns73f5vt80-a.oregon-postgres.render.com/blockflow_db_cr4e"

sqlite_engine = create_engine(f"sqlite:///{SQLITE_PATH}")
pg_engine = create_engine(POSTGRES_URL)
inspector = inspect(sqlite_engine)
tables = inspector.get_table_names()

print(f"🔄 Starting CHUNKED migration of {len(tables)} tables...")

def migrate_table_in_chunks(table_name, chunksize=50000):
    total_rows = pd.read_sql_query(f'SELECT COUNT(*) FROM {table_name}', sqlite_engine).iloc[0, 0]
    total_chunks = math.ceil(total_rows / chunksize)
    print(f"➡️  {table_name}: {total_rows} rows in {total_chunks} chunks")
    offset = 0
    for i in tqdm(range(total_chunks), desc=f"Migrating {table_name}"):
        df = pd.read_sql_query(f'SELECT * FROM {table_name} LIMIT {chunksize} OFFSET {offset}', sqlite_engine)
        df.to_sql(table_name, pg_engine, if_exists='append' if offset else 'replace', index=False)
        offset += chunksize

for table in tables:
    try:
        migrate_table_in_chunks(table)
    except Exception as e:
        print(f"❌ Error migrating {table}: {e}")

print("\n✅ Migration completed successfully! All data transferred to PostgreSQL.")
