# app/price_feed.py
"""
Simulated live price feed for Blockflow Exchange
- Streams BTCUSDT, ETHUSDT, SOLUSDT, MATICUSDT
- Updates every few seconds to mimic real volatility
- Feeds data to demo_trader.py and /api/market/orderbook
"""

import asyncio
import random
from datetime import datetime

# 🔹 Global shared dictionary (used by demo_trader & orderbook APIs)
LIVE_PRICES = {
    "BTCUSDT": 68000.0,
    "ETHUSDT": 3200.0,
    "SOLUSDT": 150.0,
    "MATICUSDT": 0.8,
}

# 🔹 Rich version for API summary display
latest_prices = {
    "BTCUSDT": {"price": 68000.0, "change": 0.0, "ts": None},
    "ETHUSDT": {"price": 3200.0, "change": 0.0, "ts": None},
    "SOLUSDT": {"price": 150.0, "change": 0.0, "ts": None},
    "MATICUSDT": {"price": 0.8, "change": 0.0, "ts": None},
}


async def run_price_feed():
    """
    Continuously simulate live price updates for all pairs.
    Broadcasts updated data to LIVE_PRICES (for demo_trader) 
    and latest_prices (for API endpoints).
    """
    print("📡 Starting simulated live price feed...")
    global LIVE_PRICES, latest_prices

    while True:
        try:
            for symbol, info in latest_prices.items():
                base = info["price"]
                change = round(random.uniform(-0.8, 0.8), 3)
                new_price = max(base * (1 + change / 100), 0.0001)

                latest_prices[symbol].update({
                    "price": round(new_price, 2),
                    "change": change,
                    "ts": datetime.utcnow().isoformat()
                })

                LIVE_PRICES[symbol] = round(new_price, 2)

            await asyncio.sleep(2)

        except Exception as e:
            print("⚠️ Price feed loop error:", e)
            await asyncio.sleep(5)


def fetch_prices():
    """
    Returns the latest price snapshot for all markets.
    Used in main.py (/api/market/orderbook) and testing endpoints.
    """
    return latest_prices
