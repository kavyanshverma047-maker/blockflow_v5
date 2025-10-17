# app/trade_engine.py
"""
Trade Execution Engine for Blockflow Exchange
Handles:
- Trade fills (market/limit)
- TP / SL logic
- Position updates
- Balance adjustments
"""

import random
import asyncio
from datetime import datetime
from app.position_manager import update_position
from app.account_service import update_balance
from app.notification_service import send_notification

async def execute_trade(user, symbol, side, qty, leverage=10, tp=None, sl=None):
    """
    Simulate a trade execution with random fill delay and price variance
    """
    print(f"[TRADE_ENGINE] Executing {side} {qty} {symbol} x{leverage}...")

    await asyncio.sleep(random.uniform(0.5, 1.5))  # simulate latency

    # Mock price fill (in real backend, this comes from orderbook)
    price = random.uniform(95, 105)

    trade = {
        "user": user,
        "symbol": symbol,
        "side": side,
        "price": round(price, 2),
        "qty": qty,
        "leverage": leverage,
        "timestamp": datetime.utcnow().isoformat(),
        "tp": tp,
        "sl": sl
    }

    # Update position in position_manager
    await update_position(trade)

    # Adjust user balance
    await update_balance(user, trade)

    # Send log/notification
    await send_notification(user, f"Trade executed: {side} {qty} {symbol} @ {trade['price']}")

    print(f"[TRADE_ENGINE ✅] {side} {symbol} trade executed successfully.")
    return trade
