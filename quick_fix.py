import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Check if old column exists
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='users' AND column_name='password_hash';
    """)
    
    if cursor.fetchone():
        print("🔧 Renaming password_hash to hashed_password...")
        cursor.execute("ALTER TABLE users RENAME COLUMN password_hash TO hashed_password;")
        conn.commit()
        print("✅ Column renamed successfully!")
    else:
        print("ℹ️ Column already correct or doesn't exist")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
