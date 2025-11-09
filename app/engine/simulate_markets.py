# -*- coding: utf-8 -*-
"""
Blockflow Market Simulator — DB-Aware Edition ⚙️
------------------------------------------------
- Simulates live market activity proportional to actual DB user count.
- Feeds WebSocket updates + live stats cache every few seconds.
- Safe for Neon/Render (auto-disables heavy writes when DISABLE_DB_WRITES=true).
"""

import asyncio
import random
import os
from datetime import datetime
from sqlalchemy.exc import OperationalError, DatabaseError
from sqlalchemy import func
from app.db import SessionLocal
from app.models import User, SpotTrade, MarginTrade, FuturesUsdmTrade
from app.engine.live_stats import stats_cache

# --------------------------------------------
# ENVIRONMENT FLAGS
# --------------------------------------------
DISABLE_DB_WRITES = os.getenv("DISABLE_DB_WRITES", "true").lower() in ("1", "true", "yes")

PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "MATICUSDT"]
PRICE_RANGES = {
    "BTCUSDT": (25000, 70000),
    "ETHUSDT": (1500, 4500),
    "SOLUSDT": (15, 250),
    "BNBUSDT": (200, 700),
    "MATICUSDT": (0.5, 2.5),
}

# Simulation parameters
TRADE_PER_USER_MIN = 1
TRADE_PER_USER_MAX = 2
MARGIN_RATIO = 0.12
FUTURES_RATIO = 0.08
SLEEP_SECONDS = 5


# --------------------------------------------
# DB & UTILS
# --------------------------------------------
def get_real_user_count():
    """Fetch user baseline from Postgres DB once."""
    db = SessionLocal()
    try:
        count = db.query(func.count(User.id)).scalar() or 0
        print(f"[Simulator] Synced {count:,} real users from DB baseline.")
        db.close()
        return count
    except Exception as e:
        print(f"[Simulator] Error fetching user count: {e}")
        db.close()
        return 500  # fallback for local dev


def safe_commit(db, objects):
    """Commit trades only if DB writes enabled."""
    if DISABLE_DB_WRITES:
        return False
    try:
        if objects:
            db.bulk_save_objects(objects)
            db.commit()
        return True
    except (OperationalError, DatabaseError) as e:
        print(f"[simulate_markets] DB write skipped due to: {e}")
        db.rollback()
        return False
    except Exception as e:
        print(f"[simulate_markets] Unexpected commit error: {e}")
        db.rollback()
        return False


# --------------------------------------------
# TRADE GENERATORS
# --------------------------------------------
def _make_spot(username: str):
    pair = random.choice(PAIRS)
    low, high = PRICE_RANGES[pair]
    return SpotTrade(
        username=username,
        pair=pair,
        side=random.choice(["buy", "sell"]),
        price=round(random.uniform(low, high), 2),
        amount=round(random.uniform(0.0005, 2.0), 5),
        timestamp=datetime.utcnow()
    )


def _make_margin(username: str):
    pair = random.choice(PAIRS)
    low, high = PRICE_RANGES[pair]
    return MarginTrade(
        username=username,
        pair=pair,
        side=random.choice(["buy", "sell"]),
        price=round(random.uniform(low, high), 2),
        amount=round(random.uniform(0.01, 3.0), 4),
        leverage=random.choice([3, 5, 10]),
        pnl=round(random.uniform(-500, 1500), 2),
        timestamp=datetime.utcnow()
    )


def _make_futures(username: str):
    pair = random.choice(PAIRS)
    low, high = PRICE_RANGES[pair]
    return FuturesUsdmTrade(
        username=username,
        pair=pair,
        side=random.choice(["long", "short"]),
        price=round(random.uniform(low, high), 2),
        amount=round(random.uniform(0.05, 10.0), 4),
        leverage=random.choice([10, 20, 50]),
        pnl=round(random.uniform(-1000, 3000), 2),
        timestamp=datetime.utcnow()
    )


# --------------------------------------------
# MAIN LOOP
# --------------------------------------------
async def simulate_markets_loop(broadcast_fn):
    """Run continuous market simulation & broadcast updates."""
    await asyncio.sleep(3)
    user_baseline = get_real_user_count()

    while True:
        db = SessionLocal()
        try:
            if user_baseline == 0:
                await asyncio.sleep(10)
                continue

            # Random slice of users
            offset = random.randint(0, max(0, user_baseline - 2000))
            users = db.query(User).offset(offset).limit(2000).all()

            spot_batch, margin_batch, futures_batch = [], [], []
            for u in users:
                for _ in range(random.randint(TRADE_PER_USER_MIN, TRADE_PER_USER_MAX)):
                    spot_batch.append(_make_spot(u.username))
                if random.random() < MARGIN_RATIO:
                    margin_batch.append(_make_margin(u.username))
                if random.random() < FUTURES_RATIO:
                    futures_batch.append(_make_futures(u.username))

            safe_commit(db, spot_batch + margin_batch + futures_batch)

            # Compute totals for display
            total_created = len(spot_batch) + len(margin_batch) + len(futures_batch)
            avg_price = random.uniform(300, 900)
            total_volume = total_created * avg_price

            # Update shared stats cache
            stats_cache.update({
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "total_users": user_baseline,
                "spot_trades": stats_cache.get("spot_trades", 0) + len(spot_batch),
                "margin_trades": stats_cache.get("margin_trades", 0) + len(margin_batch),
                "futures_usdm_trades": stats_cache.get("futures_usdm_trades", 0) + len(futures_batch),
                "total_volume_usd": stats_cache.get("total_volume_usd", 0.0) + total_volume,
            })

            # Broadcast to WebSocket clients
            summary = {
                "type": "market_update",
                "timestamp": datetime.utcnow().isoformat(),
                "users": len(users),
                "spot": len(spot_batch),
                "margin": len(margin_batch),
                "futures": len(futures_batch),
                "writes_enabled": not DISABLE_DB_WRITES,
                "total_created": total_created,
            }
            await broadcast_fn(summary)
            print(f"✅ simulate_markets_loop broadcast: {summary}")

        except Exception as e:
            db.rollback()
            print(f"[simulate_markets_loop] error: {repr(e)}")
        finally:
            db.close()

        await asyncio.sleep(SLEEP_SECONDS * random.uniform(0.9, 1.3))
