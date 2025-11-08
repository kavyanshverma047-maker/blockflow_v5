import pandas as pd
from sqlalchemy import create_engine
import math
from tqdm import tqdm

SQLITE_PATH = "blockflow.db"
POSTGRES_URL = "postgresql+psycopg2://blockflow_db_cr4e_user:PnnxFL1ioRthcz1ClMchvztuwhPeO8uT@dpg-d45ifh9r0fns73f5vt80-a.oregon-postgres.render.com/blockflow_db_cr4e"

sqlite_engine = create_engine(f"sqlite:///{SQLITE_PATH}")
pg_engine = create_engine(POSTGRES_URL)

chunksize = 50000
total_rows = pd.read_sql_query("SELECT COUNT(*) FROM users", sqlite_engine).iloc[0,0]
total_chunks = math.ceil(total_rows / chunksize)
print(f"🔄 Migrating users table: {total_rows} rows in {total_chunks} chunks")

offset = 0
for i in tqdm(range(total_chunks), desc="Migrating users"):
    df = pd.read_sql_query(f"SELECT * FROM users LIMIT {chunksize} OFFSET {offset}", sqlite_engine)
    df.to_sql("users", pg_engine, if_exists='append', index=False)
    offset += chunksize

print("✅ Done! All users migrated successfully.")
