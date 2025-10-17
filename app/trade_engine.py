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
# ============================================================
# 🔥 AUTO TP/SL MONITOR ENGINE (background async loop)
# ============================================================
import asyncio
from datetime import datetime
from app.price_feed import latest_prices
from app.models import SpotTrade, FuturesUsdmTrade, FuturesCoinmTrade
from app.utils import update_balance

async def monitor_tp_sl():
    print("🔄 TP/SL Monitor started...")
    while True:
        try:
            for model in [SpotTrade, FuturesUsdmTrade, FuturesCoinmTrade]:
                trades = model.select().where(model.is_open == True)
                for t in trades:
                    current_price = latest_prices.get(t.pair)
                    if not current_price:
                        continue

                    # ✅ TAKE PROFIT trigger
                    if t.tp and (
                        (t.side == "buy" and current_price >= t.tp) or
                        (t.side == "sell" and current_price <= t.tp)
                    ):
                        t.is_open = False
                        t.closed_at = datetime.utcnow()
                        t.pnl = (t.tp - t.entry_price) * t.amount * (1 if t.side == "buy" else -1)
                        t.save()
                        update_balance(t.username, t.pnl)
                        print(f"✅ TP hit {t.pair} ({t.side}) @ {t.tp}")

                    # ❌ STOP LOSS trigger
                    elif t.sl and (
                        (t.side == "buy" and current_price <= t.sl) or
                        (t.side == "sell" and current_price >= t.sl)
                    ):
                        t.is_open = False
                        t.closed_at = datetime.utcnow()
                        t.pnl = (t.sl - t.entry_price) * t.amount * (1 if t.side == "buy" else -1)
                        t.save()
                        update_balance(t.username, t.pnl)
                        print(f"⚠️ SL hit {t.pair} ({t.side}) @ {t.sl}")

            await asyncio.sleep(3)

        except Exception as e:
            print("❌ TP/SL Monitor Error:", e)
            await asyncio.sleep(5)

    


