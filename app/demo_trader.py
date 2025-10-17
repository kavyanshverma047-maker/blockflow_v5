# app/demo_trader.py
"""
Simulates demo trades using live prices from price_feed.py.
Creates market noise for frontend orderbooks.
"""

import asyncio, random
from datetime import datetime
from app.price_feed import LIVE_PRICES, SYMBOLS
from app.utils import random_trader_name

DEMO_TRADES = []

async def simulate_trades(broadcast_callback=None):
    """
    Periodically create demo trades using live prices.
    broadcast_callback: optional function to emit trades via websocket.
    """
    while True:
        try:
            if not LIVE_PRICES:
                await asyncio.sleep(2)
                continue

            symbol = random.choice(SYMBOLS)
            price = LIVE_PRICES.get(symbol, 0)
            side = random.choice(["BUY", "SELL"])
            amount = round(random.uniform(0.001, 0.1), 4)
            trader = random_trader_name()
            trade = {
                "symbol": symbol,
                "side": side,
                "price": price,
                "amount": amount,
                "trader": trader,
                "timestamp": datetime.utcnow().isoformat()
            }
            DEMO_TRADES.append(trade)
            print(f"💥 Demo Trade → {trade}")

            if broadcast_callback:
                await broadcast_callback(trade)

        except Exception as e:
            print("❌ Demo trader error:", e)

        await asyncio.sleep(random.uniform(3, 7))
