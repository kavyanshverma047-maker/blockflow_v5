# -*- coding: utf-8 -*-
"""
Hybrid Live Stats Updater for Blockflow
---------------------------------------
- Computes live aggregates from Postgres DB (Render)
- Stores them in in-memory cache for instant API reads
- Broadcasts updates to all connected WebSocket clients every few seconds
"""

import asyncio
import random
from datetime import datetime
from sqlalchemy import func
from app.db import SessionLocal
from app.models import (
    User, SpotTrade, MarginTrade,
    FuturesUsdmTrade, FuturesCoinmTrade,
    OptionsTrade, P2POrder,
)
from app.engine.ws_market import manager  # for broadcasting via WS

# Shared cache for quick API reads (used by admin_router)
stats_cache = {
    "timestamp": None,
    "total_users": 0,
    "spot_trades": 0,
    "margin_trades": 0,
    "futures_usdm_trades": 0,
    "futures_coinm_trades": 0,
    "options_trades": 0,
    "p2p_orders": 0,
    "total_volume_usd": 0.0,
}

REFRESH_SECONDS = 8


async def update_live_stats():
    """Continuously updates DB-driven live stats and broadcasts."""
    await asyncio.sleep(1)
    while True:
        db = SessionLocal()
        try:
            # Fetch live aggregates from Render Postgres
            total_users = db.query(func.count(User.id)).scalar() or 0
            spot_trades = db.query(func.count(SpotTrade.id)).scalar() or 0
            margin_trades = db.query(func.count(MarginTrade.id)).scalar() or 0
            fut_usdm = db.query(func.count(FuturesUsdmTrade.id)).scalar() or 0
            fut_coinm = db.query(func.count(FuturesCoinmTrade.id)).scalar() or 0
            options = db.query(func.count(OptionsTrade.id)).scalar() or 0
            p2p_orders = db.query(func.count(P2POrder.id)).scalar() or 0

            # approximate global volume for realism
            avg_price = random.uniform(300, 900)
            total_volume = (spot_trades + margin_trades + fut_usdm + fut_coinm + options) * avg_price

            stats_cache.update({
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "total_users": total_users,
                "spot_trades": spot_trades,
                "margin_trades": margin_trades,
                "futures_usdm_trades": fut_usdm,
                "futures_coinm_trades": fut_coinm,
                "options_trades": options,
                "p2p_orders": p2p_orders,
                "total_volume_usd": round(total_volume, 2),
            })

            # Print progress for monitoring
            print(
                f"[LIVE_STATS] users={total_users:,} | spot={spot_trades:,} | margin={margin_trades:,} | "
                f"futures={fut_usdm+fut_coinm:,} | total_vol=${int(total_volume):,}"
            )

            # Broadcast via WebSocket (if any active clients)
            try:
                payload = {"type": "live_stats", **stats_cache}
                await manager.broadcast(payload)
            except Exception as e:
                print(f"[live_stats] WS broadcast error: {e}")

        except Exception as e:
            print(f"[live_stats] error: {repr(e)}")
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            db.close()

        await asyncio.sleep(REFRESH_SECONDS)
