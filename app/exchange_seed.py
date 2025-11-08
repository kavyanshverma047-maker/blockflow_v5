# app/exchange_seed.py
import os
import random
import string
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

# --- Flexible imports for local + Render ---
try:
    import app.models as models
except ImportError:
    import sys
    sys.path.append(os.path.dirname(__file__))
    import models

# --- Config ---
DB_URL = os.getenv("DATABASE_URL") or "sqlite:///./demo_fallback.db"
SEED_USERS = int(os.getenv("SEED_USERS", "500"))
INITIAL_TRADES = int(os.getenv("INITIAL_TRADES", "5000"))
BATCH_SIZE = int(os.getenv("SEED_BATCH_SIZE", "500"))

# --- Engine & Session ---
engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DB_URL else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Helpers ---
def rand_name(i: Optional[int] = None) -> str:
    if i is not None:
        return f"user_{i:03d}"
    prefix = random.choice(["Alpha", "Sigma", "Nova", "Orion", "Blockflow"])
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"{prefix}_{suffix}"


def now_minus_minutes(m: int) -> datetime:
    return datetime.utcnow() - timedelta(minutes=random.randint(0, m))


def _safe_commit(db):
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print("seed: commit error:", e)


# --- Main Seeder Functions ---
def create_users_if_needed():
    db = SessionLocal()
    try:
        if not hasattr(models, "User"):
            print("seed: models.User not found — skipping user creation")
            return 0

        existing = db.query(models.User).count()
        print(f"seed: existing users: {existing}")
        if existing >= SEED_USERS:
            return existing

        to_create = SEED_USERS - existing
        print(f"seed: creating {to_create} demo users...")

        for i in range(existing, SEED_USERS):
            user = models.User(
                username=rand_name(i),
                email=f"user{i}@blockflow.demo",
                password="demo123",  # ✅ Fix: dummy password
                balance_usdt=random.uniform(1000, 10000),
                balance_inr=100000.0,
                created_at=now_minus_minutes(60 * random.randint(0, 48)),
            )
            db.add(user)
            if (i - existing + 1) % BATCH_SIZE == 0:
                _safe_commit(db)
                print(f"seed: committed {i + 1 - existing} users...")
        _safe_commit(db)
        print("✅ User seeding complete.")
        return db.query(models.User).count()
    finally:
        db.close()


def create_initial_trades():
    db = SessionLocal()
    try:
        TradeCls = getattr(models, "SpotTrade", None) or getattr(models, "Trade", None)
        if not TradeCls:
            print("seed: No Trade/SpotTrade class found — skipping.")
            return 0

        inspector = inspect(TradeCls)
        columns = {c.key for c in inspector.columns}
        print("seed: detected trade columns:", columns)

        existing = db.query(TradeCls).count()
        print(f"seed: existing trades: {existing}")
        if existing >= INITIAL_TRADES:
            return existing

        to_create = INITIAL_TRADES - existing
        print(f"seed: creating {to_create} trades...")

        for i in range(to_create):
            trade_data = {}
            if "symbol" in columns:
                trade_data["symbol"] = random.choice(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
            elif "pair" in columns:
                trade_data["pair"] = random.choice(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
            elif "market" in columns:
                trade_data["market"] = random.choice(["BTC/USDT", "ETH/USDT", "SOL/USDT"])

            if "side" in columns:
                trade_data["side"] = random.choice(["BUY", "SELL"])
            if "price" in columns:
                trade_data["price"] = random.uniform(20000, 60000)
            if "quantity" in columns:
                trade_data["quantity"] = random.uniform(0.001, 0.5)
            if "pnl" in columns:
                trade_data["pnl"] = random.uniform(-100, 300)
            if "timestamp" in columns or "created_at" in columns:
                key = "timestamp" if "timestamp" in columns else "created_at"
                trade_data[key] = datetime.utcnow()

            trade = TradeCls(**trade_data)
            db.add(trade)

            if (i + 1) % BATCH_SIZE == 0:
                _safe_commit(db)
                print(f"seed: committed {i + 1} trades...")
        _safe_commit(db)
        print("✅ Trade seeding complete.")
        return db.query(TradeCls).count()
    finally:
        db.close()


# --- Continuous Demo Loop ---
async def continuous_demo_loop(interval_min: float = 3.0):
    loop = asyncio.get_running_loop()
    print("seed: starting continuous demo trade loop...")

    def insert_fake_trade():
        db = SessionLocal()
        try:
            TradeCls = getattr(models, "SpotTrade", None)
            if not TradeCls:
                return
            trade = TradeCls(price=random.uniform(20000, 60000))
            db.add(trade)
            _safe_commit(db)
        except Exception as e:
            print("seed: continuous insert error:", e)
        finally:
            db.close()

    while True:
        await loop.run_in_executor(None, insert_fake_trade)
        await asyncio.sleep(random.uniform(interval_min, interval_min + 2))


# --- Entrypoint ---
async def seed_and_run(run_continuous=False):
    loop = asyncio.get_running_loop()
    print("seed: launching initial DB seed tasks...")
    await loop.run_in_executor(None, create_users_if_needed)
    await loop.run_in_executor(None, create_initial_trades)
    if run_continuous:
        asyncio.create_task(continuous_demo_loop())


if __name__ == "__main__":
    print("Exchange Seeder — manual run")
    asyncio.run(seed_and_run(run_continuous=False))
    print("Done.")
