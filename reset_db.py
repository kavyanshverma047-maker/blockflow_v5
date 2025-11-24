import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

print("🔥 RESETTING DATABASE...")
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cursor = conn.cursor()

cursor.execute("DROP SCHEMA public CASCADE;")
print("✅ Dropped old schema")

cursor.execute("CREATE SCHEMA public;")
cursor.execute("GRANT ALL ON SCHEMA public TO blockflow_db_cr4e_user;")
cursor.execute("GRANT ALL ON SCHEMA public TO public;")
print("✅ Created fresh schema")

cursor.close()
conn.close()
print("🎉 Database reset complete! Restart server to recreate tables.")
