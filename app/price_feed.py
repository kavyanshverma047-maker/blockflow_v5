# app/price_feed.py
"""
Simulated live price feed for Blockflow Exchange
- Updates BTCUSDT, ETHUSDT, SOLUSDT, MATICUSDT every few seconds
- Broadcasts updates via WebSocket
"""

import asyncio
import random
from datetime import datetime

# shared state
latest_prices = {
    "BTCUSDT": {"price": 64000.0, "change": 0.0, "ts": None},
    "ETHUSDT": {"price": 3200.0, "change": 0.0, "ts": None},
    "SOLUSDT": {"price": 180.0, "change": 0.0, "ts": None},
    "MATICUSDT": {"price": 0.65, "change": 0.0, "ts": None},
}

async def run_price_feed():
    """Continuously simulate price feed for all major pairs"""
    print("📡 Starting simulated live price feed...")
    while True:
        try:
            for symbol, info in latest_prices.items():
                base = info["price"]
                change = round(random.uniform(-0.5, 0.5), 3)
                new_price = max(base + (base * change / 100), 0.0001)
                latest_prices[symbol].update({
                    "price": round(new_price, 3),
                    "change": change,
                    "ts": datetime.utcnow().isoformat()
                })
            await asyncio.sleep(3)
        except Exception as e:
            print("⚠️ Price feed loop error:", e)
            await asyncio.sleep(5)

def fetch_prices():
    """Returns current snapshot for testing"""
    return latest_prices
