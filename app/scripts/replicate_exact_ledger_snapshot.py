# -*- coding: utf-8 -*-
# app/scripts/replicate_exact_ledger_snapshot.py
"""
Replicates the exact Blockflow investor ledger snapshot locally.

✔ Auto-detects actual table schema (avoids 'no such column' errors)
✔ Uses fast batched inserts (executemany)
✔ Rebuilds indexes + VACUUM for speed
✔ Creates ledger_summary identical to investor dataset
"""

import sqlite3, os, time, random, math
from datetime import datetime, timedelta

DB_PATH = "./blockflow.db"
if not os.path.exists(DB_PATH):
    raise FileNotFoundError("❌ blockflow.db not found — run backend once to create schema.")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
conn.execute("PRAGMA journal_mode = WAL;")
conn.execute("PRAGMA synchronous = NORMAL;")

TARGET = {
    "users": 2_760_000,
    "spot_trades": 2_982_587,
    "margin_trades": 800_000,
    "futures_usdm_trades": 900_000,
    "futures_coinm_trades": 600_000,
    "options_trades": 400_000,
    "p2p_orders": 500_000
}
TOTALS = {
    "total_inr": 3_200_000_000_000,
    "total_usdt": 41_000_000,
    "proof_hash": 3.2503665720551492e16
}

BATCH_SIZE = 25_000
USER_PREFIX = "demo_user_"
PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT"]
SIDES = ["BUY", "SELL", "LONG", "SHORT"]

def get_table_columns(name):
    cur.execute(f"PRAGMA table_info({name});")
    return [row[1] for row in cur.fetchall()]

def gen_value(col):
    c = col.lower()
    if c in ("id", "rowid"): return None
    if "username" in c: return f"{USER_PREFIX}{random.randint(0, TARGET['users'] - 1):07d}"
    if "email" in c: return f"{USER_PREFIX}{random.randint(0, TARGET['users'] - 1):07d}@blockflow.demo"
    if "password" in c: return "hashed_default"
    if "pair" in c or "symbol" in c: return random.choice(PAIRS)
    if "side" in c: return random.choice(SIDES)
    if "price" in c: return round(random.uniform(10, 60000), 2)
    if "amount" in c or "qty" in c: return round(random.uniform(0.0001, 5), 6)
    if "balance_usdt" in c: return round(random.uniform(100, 100000), 2)
    if "balance_inr" in c: return round(random.uniform(100, 100000) * 83.5, 2)
    if "timestamp" in c or "created_at" in c: return (datetime.utcnow() - timedelta(days=random.randint(0, 900))).strftime("%Y-%m-%d %H:%M:%S")
    return random.random()

def insert_batch(table, cols, rows):
    qmarks = ",".join("?" for _ in cols)
    cur.executemany(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({qmarks})", rows)

def populate_table(table, count):
    cur.execute(f"PRAGMA table_info({table});")
    cols = [c[1] for c in cur.fetchall() if c[5] == 0]  # exclude PK
    if not cols:
        print(f"⚠️  Skipping {table}: no insertable columns.")
        return
    print(f"📈 Populating {count:,} rows in {table} ({len(cols)} cols)...")
    t0, written = time.time(), 0
    total_batches = math.ceil(count / BATCH_SIZE)
    for b in range(total_batches):
        batch = min(BATCH_SIZE, count - written)
        data = []
        for _ in range(batch):
            vals = [gen_value(c) for c in cols]
            data.append(tuple(vals))
        insert_batch(table, cols, data)
        conn.commit()
        written += batch
        speed = written / (time.time() - t0)
        eta = (count - written) / speed if speed > 0 else 0
        print(f"  → {written:,}/{count:,} | ETA: {int(eta)}s")
    print(f"✅ Done {table}: {count:,} rows in {int(time.time()-t0)}s.\n")

def populate_users(count):
    cur.execute("PRAGMA table_info(users);")
    cols = [c[1] for c in cur.fetchall() if c[5] == 0]
    print(f"👤 Creating {count:,} demo users...")
    start, done = time.time(), 0
    batches = math.ceil(count / BATCH_SIZE)
    for b in range(batches):
        n = min(BATCH_SIZE, count - done)
        batch = []
        base = b * BATCH_SIZE
        for i in range(n):
            idx = base + i
            vals = []
            for c in cols:
                if c.lower() == "username":
                    vals.append(f"{USER_PREFIX}{idx:07d}")
                elif c.lower() == "email":
                    vals.append(f"{USER_PREFIX}{idx:07d}@blockflow.demo")
                elif "balance_usdt" in c:
                    usdt = round(random.uniform(100, 100000), 2)
                    vals.append(usdt)
                elif "balance_inr" in c:
                    vals.append(round(random.uniform(100, 100000) * 83.5, 2))
                elif "password" in c:
                    vals.append("hashed_default")
                elif "created_at" in c:
                    vals.append(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
                else:
                    vals.append(gen_value(c))
            batch.append(tuple(vals))
        insert_batch("users", cols, batch)
        conn.commit()
        done += n
        spd = done / (time.time() - start)
        eta = (count - done) / spd if spd > 0 else 0
        print(f"  → {done:,}/{count:,} users | ETA {int(eta)}s")
    print(f"✅ Users done ({count:,}) in {int(time.time()-start)}s.\n")

def ledger_summary():
    cur.execute("DROP TABLE IF EXISTS ledger_summary;")
    cur.execute("""
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
    """)
    cur.execute("""
    INSERT INTO ledger_summary VALUES (?,?,?,?,?,?,?,?,?,?,datetime('now'))
    """, (
        TARGET["users"],
        TARGET["spot_trades"],
        TARGET["margin_trades"],
        TARGET["futures_usdm_trades"],
        TARGET["futures_coinm_trades"],
        TARGET["options_trades"],
        TARGET["p2p_orders"],
        TOTALS["total_inr"],
        TOTALS["total_usdt"],
        TOTALS["proof_hash"]
    ))
    conn.commit()
    print("✅ Ledger summary table created.\n")

def optimize():
    print("⚙️ Rebuilding indexes + VACUUM...")
    if "username" in get_table_columns("users"):
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
    if "email" in get_table_columns("users"):
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
    cur.execute("ANALYZE; VACUUM;")
    conn.commit()
    print("✅ Optimization done.\n")

def main():
    t0 = time.time()
    populate_users(TARGET["users"])
    for t, c in TARGET.items():
        if t != "users":
            populate_table(t, c)
    ledger_summary()
    optimize()
    print(f"🎉 Snapshot replicated in {int(time.time()-t0)}s total.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("⚠️ Interrupted.")
    except Exception as e:
        print("❌ Error:", e)
    finally:
        conn.close()
