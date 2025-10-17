# app/exchange_seed.py
"""
Exchange Seeder (Auto-start).
- Seeds demo users if < SEED_USERS.
- Seeds INITIAL_TRADES trades across markets (batch commits).
- Starts a low-rate continuous demo trade loop using live prices if available.
- Safe for Render & SQLite (commits in batches, uses run_in_executor for heavy DB ops).
"""

import os
import random
import string
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# import your models (must exist in app.models)
try:
    import app.models as models
except Exception:
    import models  # fallback if run as script from different cwd

# Config
DB_URL = os.getenv("DATABASE_URL") or "sqlite:///./blockflow_v5.db"
SEED_USERS = int(os.getenv("SEED_USERS", "500"))
INITIAL_TRADES = int(os.getenv("INITIAL_TRADES", "5000"))
BATCH_SIZE = int(os.getenv("SEED_BATCH_SIZE", "500"))

# Create engine & sessionmaker (same pattern as main app)
engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if "sqlite" in DB_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Markets / assets to simulate
MARKETS = ["spot", "margin", "futures_usdm", "futures_coinm", "options", "p2p"]
ASSETS = ["BTC", "ETH", "SOL", "USDT", "XRP", "BNB"]

def rand_name(i: Optional[int] = None) -> str:
    if i is not None:
        return f"user_{i:03d}"
    prefix = random.choice(["Alpha","Sigma","Nova","Orion","Sovereign","Blockflow"])
    suffix = ''.join(random.choices(string.ascii_lowercase+string.digits, k=4))
    return f"{prefix}_{suffix}"

def now_minus_minutes(m: int) -> datetime:
    return datetime.utcnow() - timedelta(minutes=random.randint(0, m))

def _safe_commit(db):
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print("seed: commit error:", e)

def create_users_if_needed():
    db = SessionLocal()
    try:
        # Try to detect a User model with name / balance fields
        if not hasattr(models, "User"):
            print("seed: models.User not found — skipping user creation")
            return 0

        existing = db.query(models.User).count()
        print(f"seed: existing users: {existing}")
        if existing >= SEED_USERS:
            db.close()
            return existing

        to_create = SEED_USERS - existing
        print(f"seed: creating {to_create} demo users...")
        for i in range(existing, SEED_USERS):
            # try to adapt to model fields; common fields: name, balance_inr, created_at
            try:
                u = models.User(
                    name=rand_name(i),
                    balance_inr=random.uniform(10000, 500000),
                    created_at=now_minus_minutes(60*random.randint(0, 60))
                )
            except TypeError:
                # fallback: different constructor signature
                u = models.User()
                if hasattr(u, "name"):
                    setattr(u, "name", rand_name(i))
                if hasattr(u, "balance_inr"):
                    setattr(u, "balance_inr", random.uniform(10000, 500000))
                if hasattr(u, "created_at"):
                    setattr(u, "created_at", now_minus_minutes(60*random.randint(0, 60)))
            db.add(u)
            if (i - existing + 1) % BATCH_SIZE == 0:
                _safe_commit(db)
                print(f"seed: committed {i+1-existing} users...")
        _safe_commit(db)
        print("seed: user seeding complete")
        return db.query(models.User).count()
    finally:
        db.close()

def create_initial_trades():
    db = SessionLocal()
    try:
        # try to find a Trade-like model
        TradeCls = getattr(models, "Trade", None)
        if TradeCls is None:
            # also check for common specific names
            TradeCls = getattr(models, "SpotTrade", None) or getattr(models, "FuturesTrade", None)
        if TradeCls is None:
            print("seed: No Trade class found in models. Skipping initial trades.")
            return 0

        existing_trades = db.query(TradeCls).count()
        print(f"seed: existing trades: {existing_trades}")
        to_create = max(0, INITIAL_TRADES - existing_trades)
        if to_create == 0:
            print("seed: already enough trades, skipping initial trade seed.")
            return existing_trades

        print(f"seed: creating {to_create} initial trades (this may take a moment)...")
        for i in range(to_create):
            market = random.choice(MARKETS)
            asset = random.choice(ASSETS)
            side = random.choice(["buy", "sell"])
            price = round(random.uniform(1000, 70000), 2)
            amount = round(random.uniform(0.001, 2.5), 4)
            pnl = round(random.uniform(-500, 1500), 2)
            timestamp = now_minus_minutes(720)

            # try to map fields
            try:
                trade = TradeCls(
                    user=rand_name(random.randint(0, SEED_USERS-1)),
                    market=market,
                    asset=asset,
                    side=side,
                    price=price,
                    amount=amount,
                    pnl=pnl,
                    created_at=timestamp
                )
            except TypeError:
                # fallback set attributes dynamically
                trade = TradeCls()
                for k,v in {
                    "user": rand_name(random.randint(0, SEED_USERS-1)),
                    "market": market, "asset": asset, "side": side,
                    "price": price, "amount": amount, "pnl": pnl,
                    "created_at": timestamp
                }.items():
                    if hasattr(trade, k):
                        try:
                            setattr(trade, k, v)
                        except Exception:
                            pass
            db.add(trade)
            if (i+1) % BATCH_SIZE == 0:
                _safe_commit(db)
                print(f"seed: committed {i+1} trades...")
        _safe_commit(db)
        total = db.query(TradeCls).count()
        print(f"seed: initial trade seeding complete. total trades now: {total}")
        return total
    finally:
        db.close()

async def continuous_demo_loop(interval_min: float = 3.0, broadcast_callback=None):
    """
    Non-blocking demo loop: periodically insert small trades to keep UI alive.
    Uses run_in_executor to perform DB writes so as not to block event loop.
    """
    loop = asyncio.get_running_loop()
    def db_insert_one_fake_trade():
        db = SessionLocal()
        try:
            TradeCls = getattr(models, "Trade", None)
            if TradeCls is None:
                TradeCls = getattr(models, "SpotTrade", None) or getattr(models, "FuturesTrade", None)
            if TradeCls is None:
                return None
            market = random.choice(MARKETS)
            asset = random.choice(ASSETS)
            side = random.choice(["buy", "sell"])
            price = round(random.uniform(1000, 70000), 2)
            amount = round(random.uniform(0.0001, 0.2), 4)
            timestamp = datetime.utcnow()
            try:
                t = TradeCls(
                    user=rand_name(random.randint(0, SEED_USERS-1)),
                    market=market, asset=asset, side=side,
                    price=price, amount=amount, pnl=round(random.uniform(-20, 50),2),
                    created_at=timestamp
                )
            except TypeError:
                t = TradeCls()
                for k,v in {
                    "user": rand_name(random.randint(0, SEED_USERS-1)),
                    "market": market, "asset": asset, "side": side,
                    "price": price, "amount": amount, "pnl": round(random.uniform(-20,50),2),
                    "created_at": timestamp
                }.items():
                    if hasattr(t, k):
                        try: setattr(t, k, v)
                        except Exception: pass
            db.add(t)
            _safe_commit(db)
            return {
                "user": getattr(t, "user", None),
                "market": getattr(t, "market", None),
                "asset": getattr(t, "asset", None),
                "side": getattr(t, "side", None),
                "price": getattr(t, "price", None),
                "amount": getattr(t, "amount", None),
                "created_at": getattr(t, "created_at", None),
            }
        except Exception as e:
            print("seed: continuous db insert error:", e)
        finally:
            db.close()

    print("seed: starting continuous demo trade loop (interval approx %.1fs)..." % interval_min)
    while True:
        try:
            res = await loop.run_in_executor(None, db_insert_one_fake_trade)
            if res:
                # Optionally broadcast via websocket: callback should be an async fn
                if broadcast_callback:
                    try:
                        await broadcast_callback(res)
                    except Exception as e:
                        print("seed: broadcast callback error:", e)
            await asyncio.sleep(random.uniform(interval_min, interval_min + 3.0))
        except asyncio.CancelledError:
            print("seed: demo loop cancelled")
            return
        except Exception as e:
            print("seed: continuous loop error:", e)
            await asyncio.sleep(2.0)


async def seed_and_run(broadcast_callback=None, run_continuous=True):
    """
    Public entrypoint: performs initial seeding synchronously (but not blocking event loop),
    then optionally starts continuous demo loop in background.
    """
    loop = asyncio.get_running_loop()
    print("seed: launching initial DB seed tasks...")
    # Run the heavy DB operations in threadpool so startup isn't blocked
    await loop.run_in_executor(None, create_users_if_needed)
    await loop.run_in_executor(None, create_initial_trades)

    if run_continuous:
        # start the continuous loop as a background task (non-blocking)
        task = asyncio.create_task(continuous_demo_loop(interval_min=3.0, broadcast_callback=broadcast_callback))
        print("seed: continuous demo loop started (task id: %s)" % id(task))
        return task
    return None


# If called directly:
if __name__ == "__main__":
    print("Exchange Seeder — manual run")
    asyncio.run(seed_and_run(run_continuous=False))
    print("Done.")
