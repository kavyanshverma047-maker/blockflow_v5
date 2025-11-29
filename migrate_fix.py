# migrate_fix.py
"""
Complete database migration script
Fixes ledger and wallet tables to match new schema
Run: python migrate_fix.py
"""

import os
from sqlalchemy import create_engine, text, inspect
from app.db import DATABASE_URL

print("🚀 Starting database migration...")
print(f"📍 Database: {DATABASE_URL[:50]}...")

engine = create_engine(DATABASE_URL)

def table_exists(table_name):
    """Check if table exists"""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()

def column_exists(table_name, column_name):
    """Check if column exists in table"""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

with engine.begin() as conn:
    print("\n📋 Step 1: Checking wallets table...")
    
    if table_exists('wallets'):
        # Drop old columns if they exist
        if column_exists('wallets', 'username'):
            print("   ➜ Dropping old 'username' column...")
            conn.execute(text("ALTER TABLE wallets DROP COLUMN username"))
        
        if column_exists('wallets', 'balance'):
            print("   ➜ Dropping old 'balance' column...")
            conn.execute(text("ALTER TABLE wallets DROP COLUMN balance"))
        
        # Add new columns if they don't exist
        if not column_exists('wallets', 'user_id'):
            print("   ➜ Adding 'user_id' column...")
            conn.execute(text("ALTER TABLE wallets ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0"))
        
        if not column_exists('wallets', 'currency'):
            print("   ➜ Adding 'currency' column...")
            conn.execute(text("ALTER TABLE wallets ADD COLUMN currency VARCHAR(10) NOT NULL DEFAULT 'INR'"))
        
        if not column_exists('wallets', 'available'):
            print("   ➜ Adding 'available' column...")
            conn.execute(text("ALTER TABLE wallets ADD COLUMN available NUMERIC(20,8) NOT NULL DEFAULT 0"))
        
        if not column_exists('wallets', 'reserved'):
            print("   ➜ Adding 'reserved' column...")
            conn.execute(text("ALTER TABLE wallets ADD COLUMN reserved NUMERIC(20,8) NOT NULL DEFAULT 0"))
        
        if not column_exists('wallets', 'updated_at'):
            print("   ➜ Adding 'updated_at' column...")
            conn.execute(text("ALTER TABLE wallets ADD COLUMN updated_at TIMESTAMP DEFAULT NOW()"))
        
        # Add unique constraint
        print("   ➜ Adding unique constraint...")
        try:
            conn.execute(text("ALTER TABLE wallets DROP CONSTRAINT IF EXISTS uq_user_currency"))
            conn.execute(text("ALTER TABLE wallets ADD CONSTRAINT uq_user_currency UNIQUE (user_id, currency)"))
        except Exception as e:
            print(f"      ⚠️  Constraint warning: {e}")
        
        print("   ✅ Wallets table fixed!")
    else:
        print("   ⚠️  Wallets table doesn't exist, will be created later")
    
    print("\n📋 Step 2: Checking ledger table...")
    
    if table_exists('ledger'):
        # Drop old columns if they exist
        if column_exists('ledger', 'username'):
            print("   ➜ Dropping old 'username' column...")
            conn.execute(text("ALTER TABLE ledger DROP COLUMN username"))
        
        if column_exists('ledger', 'type'):
            print("   ➜ Dropping old 'type' column...")
            conn.execute(text("ALTER TABLE ledger DROP COLUMN type"))
        
        # Add new columns if they don't exist
        if not column_exists('ledger', 'tx_id'):
            print("   ➜ Adding 'tx_id' column...")
            conn.execute(text("ALTER TABLE ledger ADD COLUMN tx_id VARCHAR(100) NOT NULL DEFAULT ''"))
        
        if not column_exists('ledger', 'account'):
            print("   ➜ Adding 'account' column...")
            conn.execute(text("ALTER TABLE ledger ADD COLUMN account VARCHAR(200) NOT NULL DEFAULT ''"))
        
        if not column_exists('ledger', 'entry_type'):
            print("   ➜ Adding 'entry_type' column...")
            conn.execute(text("ALTER TABLE ledger ADD COLUMN entry_type VARCHAR(10) NOT NULL DEFAULT 'credit'"))
        
        if not column_exists('ledger', 'ref'):
            print("   ➜ Adding 'ref' column...")
            conn.execute(text("ALTER TABLE ledger ADD COLUMN ref VARCHAR(100)"))
        
        if not column_exists('ledger', 'timestamp'):
            print("   ➜ Adding 'timestamp' column...")
            conn.execute(text("ALTER TABLE ledger ADD COLUMN timestamp TIMESTAMP DEFAULT NOW()"))
        
        print("   ✅ Ledger table fixed!")
    else:
        print("   ⚠️  Ledger table doesn't exist, will be created later")
    
    print("\n📋 Step 3: Adding indexes...")
    
    # Add indexes (ignore if they already exist)
    try:
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ledger_tx_id ON ledger(tx_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ledger_account ON ledger(account)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ledger_timestamp ON ledger(timestamp)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_wallet_user_id ON wallets(user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_wallet_currency ON wallets(currency)"))
        print("   ✅ Indexes created!")
    except Exception as e:
        print(f"   ⚠️  Index warning: {e}")

print("\n📋 Step 4: Creating missing tables...")
from app.db import Base
Base.metadata.create_all(bind=engine)
print("   ✅ All missing tables created!")

print("\n🎉 Migration completed successfully!")
print("\n📝 Next steps:")
print("   1. Run: pytest tests/test_ledger_reconcile.py -v")
print("   2. If tests pass, start server: python -m uvicorn app.main:app --reload")
