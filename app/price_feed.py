# app/price_feed.py
"""
Fetches live crypto prices from Binance and stores them in a shared dictionary.
Runs automatically from main.py on startup.
"""

import asyncio, httpx
from datetime import datetime

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
LIVE_PRICES = {}

async def fetch_prices():
    async with httpx.AsyncClient() as client:
        while True:
            try:
                for symbol in SYMBOLS:
                    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
                    r = await client.get(url, timeout=5.0)
                    data = r.json()
                    LIVE_PRICES[symbol] = float(data["price"])
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Updated prices: {LIVE_PRICES}")
            except Exception as e:
                print("❌ Price feed error:", e)
            await asyncio.sleep(3)
