# app/engine/simulate_markets.py
"""
Real-time market simulator.
- Rotates through users in random offsets so all seeded users get trades over time.
- Commits in batches and sleeps to avoid overloading DB.
- Safe for running as an async background task in FastAPI startup.
"""

import asyncio
import random
import math
from datetime import datetime, timedelta
from typing import List

from app.db import SessionLocal
from app.models import User, SpotTrade, MarginTrade, FuturesUsdmTrade

PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "MATICUSDT"]
PRICE_RANGES = {
    "BTCUSDT": (25000, 70000),
    "ETHUSDT": (1500, 4500),
    "SOLUSDT": (15, 250),
    "BNBUSDT": (200, 700),
    "MATICUSDT": (0.5, 2.5),
}

BATCH_USER_COUNT = 2000        # how many users to touch per iteration
TRADE_PER_USER_MIN = 1
TRADE_PER_USER_MAX = 2
MARGIN_RATIO = 0.12            # fraction of users doing margin trades in batch
FUTURES_RATIO = 0.08           # fraction of users doing futures trades in batch
SLEEP_SECONDS = 4              # loop delay (tune for load)

def _make_spot(username: str):
    pair = random.choice(PAIRS)
    low, high = PRICE_RANGES[pair]
    side = random.choice(["buy", "sell"])
    price = round(random.uniform(low, high), 2)
    amount = round(random.uniform(0.0005, 2.0), 5)
    ts = datetime.utcnow() - timedelta(seconds=random.randint(0, 3600))
    return SpotTrade(username=username, pair=pair, side=side, price=price, amount=amount, timestamp=ts)

def _make_margin(username: str):
    pair = random.choice(PAIRS)
    low, high = PRICE_RANGES[pair]
    side = random.choice(["buy", "sell"])
    price = round(random.uniform(low, high), 2)
    amount = round(random.uniform(0.01, 3.0), 4)
    leverage = random.choice([3,5,10])
    pnl = round(random.uniform(-500, 1500), 2)
    ts = datetime.utcnow() - timedelta(seconds=random.randint(0, 3600))
    return MarginTrade(username=username, pair=pair, side=side, price=price, amount=amount, leverage=leverage, pnl=pnl, timestamp=ts)

def _make_futures(username: str):
    pair = random.choice(PAIRS)
    low, high = PRICE_RANGES[pair]
    side = random.choice(["long", "short"])
    price = round(random.uniform(low, high), 2)
    amount = round(random.uniform(0.05, 10.0), 4)
    leverage = random.choice([10,20,50])
    pnl = round(random.uniform(-1000, 3000), 2)
    ts = datetime.utcnow() - timedelta(seconds=random.randint(0, 3600))
    return FuturesUsdmTrade(username=username, pair=pair, side=side, price=price, amount=amount, leverage=leverage, pnl=pnl, timestamp=ts)

async def simulate_markets():
    """
    Main async loop. Use asyncio.create_task(simulate_markets()) from FastAPI startup.
    """
    await asyncio.sleep(2)  # slight startup delay
    while True:
        db = SessionLocal()
        try:
            total_users = db.query(User).count()
            if total_users == 0:
                print("simulate_markets: no users found, sleeping...")
                db.close()
                await asyncio.sleep(10)
                continue

            # choose a random offset so batches cover entire user table over time
            max_offset = max(0, total_users - BATCH_USER_COUNT)
            offset = random.randint(0, max_offset)
            users = db.query(User).offset(offset).limit(BATCH_USER_COUNT).all()

            spot_batch: List = []
            margin_batch: List = []
            futures_batch: List = []

            for u in users:
                trades_to_make = random.randint(TRADE_PER_USER_MIN, TRADE_PER_USER_MAX)
                for _ in range(trades_to_make):
                    spot_batch.append(_make_spot(u.username))

                if random.random() < MARGIN_RATIO:
                    margin_batch.append(_make_margin(u.username))

                if random.random() < FUTURES_RATIO:
                    futures_batch.append(_make_futures(u.username))

                # small balance update to simulate PnL; tiny change to avoid wiping balances
                try:
                    delta = round(random.uniform(-2.5, 6.5), 4)
                    u.balance_usdt = max(0.0, (u.balance_usdt or 0.0) + delta)
                except Exception:
                    # defensive: if model lacks balance_usdt
                    pass

            # bulk persist
            if spot_batch:
                db.bulk_save_objects(spot_batch)
            if margin_batch:
                db.bulk_save_objects(margin_batch)
            if futures_batch:
                db.bulk_save_objects(futures_batch)

            db.commit()

            total_created = len(spot_batch) + len(margin_batch) + len(futures_batch)
            print(f"simulate_markets: offset={offset:,} users={len(users):,} created_trades={total_created:,}")

        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            print("simulate_markets error:", repr(e))
        finally:
            db.close()

        # small randomized sleep to avoid perfect cadence
        jitter = random.uniform(0.8, 1.25)
        await asyncio.sleep(SLEEP_SECONDS * jitter)

if __name__ == "__main__":
    # run standalone for local debugging
    import asyncio as _asyncio
    _asyncio.run(simulate_markets())

