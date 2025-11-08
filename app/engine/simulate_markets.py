"""
Blockflow Market Simulator — Investor-Safe Edition ✅
Keeps live price movements & WebSocket updates but avoids DB writes when DB is full.

- Generates pseudo-trades for Spot, Margin, Futures (read-only demo)
- Broadcasts live market updates for frontend visual activity
- Safe for Neon free-tier (512 MB) — avoids inserts when DISABLE_DB_WRITES=true
"""

import asyncio
import random
from datetime import datetime, timedelta
from app.db import SessionLocal
from app.models import User, SpotTrade, MarginTrade, FuturesUsdmTrade
from sqlalchemy.exc import OperationalError, DatabaseError
import os

# ----------------------------
# ENV TOGGLE (edit .env)
# ----------------------------
DISABLE_DB_WRITES = os.getenv("DISABLE_DB_WRITES", "true").lower() in ("1", "true", "yes")

PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "MATICUSDT"]
PRICE_RANGES = {
    "BTCUSDT": (25000, 70000),
    "ETHUSDT": (1500, 4500),
    "SOLUSDT": (15, 250),
    "BNBUSDT": (200, 700),
    "MATICUSDT": (0.5, 2.5),
}

BATCH_USER_COUNT = 2000
TRADE_PER_USER_MIN = 1
TRADE_PER_USER_MAX = 2
MARGIN_RATIO = 0.12
FUTURES_RATIO = 0.08
SLEEP_SECONDS = 5


# ----------------------------
# Trade generators
# ----------------------------
def _make_spot(username: str):
    pair = random.choice(PAIRS)
    low, high = PRICE_RANGES[pair]
    side = random.choice(["buy", "sell"])
    price = round(random.uniform(low, high), 2)
    amount = round(random.uniform(0.0005, 2.0), 5)
    ts = datetime.utcnow()
    return SpotTrade(username=username, pair=pair, side=side, price=price, amount=amount, timestamp=ts)

def _make_margin(username: str):
    pair = random.choice(PAIRS)
    low, high = PRICE_RANGES[pair]
    side = random.choice(["buy", "sell"])
    price = round(random.uniform(low, high), 2)
    amount = round(random.uniform(0.01, 3.0), 4)
    leverage = random.choice([3, 5, 10])
    pnl = round(random.uniform(-500, 1500), 2)
    ts = datetime.utcnow()
    return MarginTrade(username=username, pair=pair, side=side, price=price, amount=amount, leverage=leverage, pnl=pnl, timestamp=ts)

def _make_futures(username: str):
    pair = random.choice(PAIRS)
    low, high = PRICE_RANGES[pair]
    side = random.choice(["long", "short"])
    price = round(random.uniform(low, high), 2)
    amount = round(random.uniform(0.05, 10.0), 4)
    leverage = random.choice([10, 20, 50])
    pnl = round(random.uniform(-1000, 3000), 2)
    ts = datetime.utcnow()
    return FuturesUsdmTrade(username=username, pair=pair, side=side, price=price, amount=amount, leverage=leverage, pnl=pnl, timestamp=ts)


# ----------------------------
# Safe DB write helper
# ----------------------------
def safe_commit(db, objects):
    """Try committing trades; skip if disabled or DB full."""
    if DISABLE_DB_WRITES:
        return False
    try:
        if objects:
            db.bulk_save_objects(objects)
            db.commit()
        return True
    except (OperationalError, DatabaseError) as e:
        print(f"[simulate_markets] DB write skipped due to: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return False
    except Exception as e:
        print(f"[simulate_markets] Unexpected commit error: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return False


# ----------------------------
# Main async loop
# ----------------------------
async def simulate_markets_loop(broadcast_fn):
    """Continuously simulate markets and broadcast summaries."""
    await asyncio.sleep(3)
    while True:
        db = SessionLocal()
        try:
            total_users = db.query(User).count()
            if total_users == 0:
                db.close()
                await asyncio.sleep(10)
                continue

            offset = random.randint(0, max(0, total_users - BATCH_USER_COUNT))
            users = db.query(User).offset(offset).limit(BATCH_USER_COUNT).all()

            spot_batch, margin_batch, futures_batch = [], [], []

            for u in users:
                for _ in range(random.randint(TRADE_PER_USER_MIN, TRADE_PER_USER_MAX)):
                    spot_batch.append(_make_spot(u.username))
                if random.random() < MARGIN_RATIO:
                    margin_batch.append(_make_margin(u.username))
                if random.random() < FUTURES_RATIO:
                    futures_batch.append(_make_futures(u.username))

                # simulate price balance drift
                try:
                    delta = round(random.uniform(-2.5, 6.5), 4)
                    u.balance_usdt = max(0.0, (u.balance_usdt or 0.0) + delta)
                except Exception:
                    pass

            # Attempt safe DB write (only if enabled)
            safe_commit(db, spot_batch + margin_batch + futures_batch)

            # Broadcast visual update (even if DB write skipped)
            total_created = len(spot_batch) + len(margin_batch) + len(futures_batch)
            summary = {
                "type": "market_update",
                "timestamp": datetime.utcnow().isoformat(),
                "offset": offset,
                "users": len(users),
                "spot": len(spot_batch),
                "margin": len(margin_batch),
                "futures": len(futures_batch),
                "writes_enabled": not DISABLE_DB_WRITES,
                "total_created": total_created
            }
            await broadcast_fn(summary)
            print(f"✅ simulate_markets_loop broadcast: {summary}")

        except Exception as e:
            db.rollback()
            print(f"[simulate_markets_loop] error: {repr(e)}")
        finally:
            db.close()

        await asyncio.sleep(SLEEP_SECONDS * random.uniform(0.8, 1.25))
