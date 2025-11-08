"""
Blockflow Half-Dataset Seeder (Universal)
------------------------------------
Works for both PostgreSQL and SQLite.
Populates ~1.35M users and proportional trades.
"""

import os, random, time
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./blockflow.db")
engine = create_engine(DATABASE_URL)
dialect = "sqlite" if "sqlite" in DATABASE_URL else "postgres"

print(f"✅ Connected to {dialect.upper()} database.")
conn = engine.connect()
start = time.time()

# Target counts
target = {
    "users": 1_380_000,
    "spot_trades": 1_491_000,
    "margin_trades": 400_000,
    "futures_usdm": 450_000,
    "futures_coinm": 300_000,
    "options_trades": 200_000,
    "p2p_orders": 250_000
}

totals = {
    "total_inr": 1_600_000_000_000,
    "total_usdt": 20_500_000,
    "proof_hash": 1.6251832860275746e16
}

# Create tables if missing
print("🧱 Ensuring tables exist...")
conn.execute(text("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    email TEXT,
    password TEXT,
    balance_usdt REAL,
    balance_inr REAL,
    created_at TEXT
);
"""))
for t in ["spot_trades","margin_trades","futures_usdm_trades",
          "futures_coinm_trades","options_trades","p2p_orders"]:
    conn.execute(text(f"""
    CREATE TABLE IF NOT EXISTS {t} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        price REAL,
        volume REAL
    );
    """))
conn.commit()

# Clear tables
print("🧹 Clearing old data...")
for t in ["users","spot_trades","margin_trades","futures_usdm_trades",
          "futures_coinm_trades","options_trades","p2p_orders"]:
    try:
        if dialect == "postgres":
            conn.execute(text(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE;"))
        else:
            conn.execute(text(f"DELETE FROM {t};"))
    except Exception as e:
        print(f"⚠️ Skip clearing {t}: {e}")
conn.commit()

# Users
print(f"\n👤 Inserting {target['users']:,} demo users...")
user_stmt = text("""
INSERT INTO users (username, email, password, balance_usdt, balance_inr, created_at)
VALUES (:username, :email, :password, :balance_usdt, :balance_inr, datetime('now'))
""" if dialect=="sqlite" else """
INSERT INTO users (username, email, password, balance_usdt, balance_inr, created_at)
VALUES (:username, :email, :password, :balance_usdt, :balance_inr, NOW())
""")

batch = []
for i in range(target["users"]):
    batch.append({
        "username": f"demo_user_{i:07d}",
        "email": f"user{i}@blockflow.demo",
        "password": "hashed_default",
        "balance_usdt": round(random.uniform(50, 20000), 2),
        "balance_inr": round(random.uniform(1000, 1_000_000), 2)
    })
    if len(batch) >= 10000:
        conn.execute(user_stmt, batch)
        conn.commit()
        print(f"  → {i:,} users inserted...")
        batch = []
if batch:
    conn.execute(user_stmt, batch)
    conn.commit()
print("✅ Users complete.\n")

# Generic seeding
def seed_table(name, count):
    print(f"📈 Seeding {count:,} rows into {name}...")
    stmt = text("INSERT INTO "+name+" (price, volume) VALUES (:price, :volume)")
    batch=[]
    for i in range(count):
        batch.append({
            "price": round(random.uniform(10, 100000),2),
            "volume": round(random.uniform(0.01,5),3)
        })
        if len(batch)>=10000:
            conn.execute(stmt,batch)
            conn.commit()
            print(f"  → {i:,} rows...")
            batch=[]
    if batch:
        conn.execute(stmt,batch)
        conn.commit()
    print(f"✅ Done seeding {name}.\n")

for t,c in [
    ("spot_trades",target["spot_trades"]),
    ("margin_trades",target["margin_trades"]),
    ("futures_usdm_trades",target["futures_usdm"]),
    ("futures_coinm_trades",target["futures_coinm"]),
    ("options_trades",target["options_trades"]),
    ("p2p_orders",target["p2p_orders"])
]:
    seed_table(t,c)

# Ledger summary
conn.execute(text("DROP TABLE IF EXISTS ledger_summary;"))
conn.execute(text("""
CREATE TABLE ledger_summary (
    total_users INTEGER,
    spot_trades INTEGER,
    margin_trades INTEGER,
    futures_usdm INTEGER,
    futures_coinm INTEGER,
    options_trades INTEGER,
    p2p_orders INTEGER,
    total_inr REAL,
    total_usdt REAL,
    proof_hash REAL,
    updated_at TEXT
);
"""))
conn.execute(text("""
INSERT INTO ledger_summary VALUES (
:users,:spot,:margin,:usdm,:coinm,:opt,:p2p,:inr,:usdt,:hash,datetime('now')
);
"""),{
    "users":target["users"],
    "spot":target["spot_trades"],
    "margin":target["margin_trades"],
    "usdm":target["futures_usdm"],
    "coinm":target["futures_coinm"],
    "opt":target["options_trades"],
    "p2p":target["p2p_orders"],
    "inr":totals["total_inr"],
    "usdt":totals["total_usdt"],
    "hash":totals["proof_hash"]
})
conn.commit()

print(f"🎯 Seeder complete in {round(time.time()-start,1)}s.")
conn.close()
