# app/liquidity_engine.py
"""
Lightweight liquidity pool simulator for Blockflow.
Simulates aggregated pool metrics for many users (10M demo) without
simulating each user individually.
Run via a background asyncio task on app startup.
"""

import asyncio
import random
from datetime import datetime
from typing import Dict

# initial base reserves / approximate values (USD / pair-level approx)
POOL: Dict[str, Dict] = {
    "BTC_USDT": {
        "liquidity_usd": 520_000_000,  # virtual liquidity in USD
        "spread_pct": 0.08,
        "volume_24h_usd": 26_000_000,
        "open_interest_usd": 42_000_000,
        "funding_rate_pct": 0.0003,
    },
    "ETH_USDT": {
        "liquidity_usd": 310_000_000,
        "spread_pct": 0.09,
        "volume_24h_usd": 12_000_000,
        "open_interest_usd": 23_000_000,
        "funding_rate_pct": 0.00025,
    },
    "USDT_POOL": {
        "liquidity_usd": 1_250_000_000
    }
}

# aggregate meta
POOL_META = {
    "users_simulated": 10_000_000,
    "avg_balance_usd": 128.5,
    "active_ratio": 0.021,  # ~2.1% active at any time
    "last_update": None
}

# Safety: control update cadence and amplitude
_UPDATE_INTERVAL_SECONDS = 10
_MAX_PCT_MOVE_PER_UPDATE = 0.0025  # <=0.25% typical per tick

# internal flag used for tests / graceful shutdown
_running = True


def get_pool_state() -> Dict:
    """Return a snapshot of the current pool state for the API / frontend."""
    snapshot = {
        "meta": {
            "users_simulated": POOL_META["users_simulated"],
            "avg_balance_usd": POOL_META["avg_balance_usd"],
            "active_ratio": POOL_META["active_ratio"],
            "estimated_total_liquidity_usd": int(sum(p.get("liquidity_usd", 0) for p in POOL.values())),
            "last_update": POOL_META["last_update"],
        },
        "pairs": {},
    }

    for pair, s in POOL.items():
        snapshot["pairs"][pair] = {
            "liquidity_usd": int(s.get("liquidity_usd", 0)),
            "spread_pct": round(s.get("spread_pct", 0), 4),
            "volume_24h_usd": int(s.get("volume_24h_usd", 0)),
            "open_interest_usd": int(s.get("open_interest_usd", 0)),
            "funding_rate_pct": round(s.get("funding_rate_pct", 0), 8),
            "last_update": s.get("last_update"),
        }

    return snapshot


async def simulate_liquidity_loop():
    """Background loop updating the pool in memory."""
    global _running
    while _running:
        # small random walk per market, bounded
        for pair, s in POOL.items():
            # liquidity moves slightly depending on activity
            liquidity = s.get("liquidity_usd", 0)
            vol = s.get("volume_24h_usd", 0)
            oi = s.get("open_interest_usd", 0)

            # percent changes
            liquidity_change_pct = random.uniform(-_MAX_PCT_MOVE_PER_UPDATE, _MAX_PCT_MOVE_PER_UPDATE)
            vol_change_pct = random.uniform(-_MAX_PCT_MOVE_PER_UPDATE * 4, _MAX_PCT_MOVE_PER_UPDATE * 4)
            oi_change_pct = random.uniform(-_MAX_PCT_MOVE_PER_UPDATE * 3, _MAX_PCT_MOVE_PER_UPDATE * 3)
            spread_noise = random.uniform(-0.002, 0.002)
            funding_noise = random.uniform(-0.00002, 0.00002)

            # apply changes
            s["liquidity_usd"] = max(0, liquidity * (1 + liquidity_change_pct))
            s["volume_24h_usd"] = max(0, vol * (1 + vol_change_pct))
            s["open_interest_usd"] = max(0, oi * (1 + oi_change_pct))

            # spread and funding rate jitter
            s["spread_pct"] = round(max(0.001, s.get("spread_pct", 0.05) + spread_noise), 6)
            s["funding_rate_pct"] = round(max(-0.001, s.get("funding_rate_pct", 0.0001) + funding_noise), 8)

            s["last_update"] = datetime.utcnow().isoformat() + "Z"

        # update meta
        POOL_META["last_update"] = datetime.utcnow().isoformat() + "Z"

        # light-weight bookkeeping (no DB writes by default; you can extend)
        await asyncio.sleep(_UPDATE_INTERVAL_SECONDS)


def stop_simulation():
    """Signal the background loop to stop (useful in tests)."""
    global _running
    _running = False
