# app/trade_engine.py
"""
Trade engine helpers:
 - execute_trade(...) : core function that simulates/exectues a trade and calls position updates
 - monitor_tp_sl() : background loop that scans open positions/orders and triggers TP/SL fills
This file uses lazy imports for position_manager to avoid circular imports.
"""

import asyncio
import traceback
from typing import Dict, Any, Optional

# If your project has SessionLocal / models, try to import them lazily inside functions.
try:
    from app.db import SessionLocal
    from app import models
except Exception:
    SessionLocal = None
    models = None


async def execute_trade(user_id: int,
                        symbol: str,
                        side: str,
                        price: float,
                        quantity: float,
                        order_type: str = "market",
                        take_profit: Optional[float] = None,
                        stop_loss: Optional[float] = None) -> Dict[str, Any]:
    """
    Execute a trade (demo/simulated). After execution, update positions and register TP/SL if provided.
    This is the function the API endpoints call to place orders.
    """
    try:
        # Simulate fill - in real engine you'd match against orderbook/liquidity
        fill_price = float(price)
        fill_qty = float(quantity)

        # Build trade record (DB insert if available)
        trade_record = None
        if SessionLocal and models:
            session = SessionLocal()
            try:
                t = models.SpotTrade(user_id=user_id, symbol=symbol, side=side, price=fill_price, amount=fill_qty, order_type=order_type)
                session.add(t)
                session.commit()
                trade_record = {"id": t.id}
            except Exception as e:
                print("⚠️ trade_engine: could not write SpotTrade:", e)
            finally:
                try:
                    session.close()
                except Exception:
                    pass

        # Update user position (lazy import)
        try:
            from app.position_manager import update_position
        except Exception as e:
            print("⚠️ trade_engine: lazy import update_position failed:", e)
            update_position = None

        if update_position:
            try:
                res = await update_position(user_id, symbol, side, fill_qty, fill_price)
                # log / attach result
            except Exception as e:
                print("❌ trade_engine.update_position error:", e)

        # Register TP/SL (store in DB or in-memory registry)
        if (take_profit or stop_loss) and SessionLocal and models:
            try:
                session = SessionLocal()
                # example: create a trigger row in DB so monitor_tp_sl can find it
                trig = models.TPTrigger(user_id=user_id, symbol=symbol, side=side,
                                        tp=take_profit if take_profit else None,
                                        sl=stop_loss if stop_loss else None,
                                        active=True, created_at=asyncio.get_event_loop().time())
                session.add(trig)
                session.commit()
                try:
                    session.close()
                except Exception:
                    pass
            except Exception as e:
                print("⚠️ trade_engine: could not register TP/SL trigger:", e)

        result = {
            "ok": True,
            "filled_price": fill_price,
            "filled_qty": fill_qty,
            "trade_record": trade_record
        }
        return result
    except Exception as e:
        traceback.print_exc()
        return {"ok": False, "error": str(e)}


async def _fetch_latest_price(symbol: str) -> Optional[float]:
    """
    Small helper to fetch latest price snapshot.
    Tries to import price feed or call API endpoint. Non-blocking.
    """
    try:
        # Try local module
        from app.price_feed import fetch_prices
        data = fetch_prices()
        if isinstance(data, dict) and symbol in data:
            return float(data[symbol]["price"])
    except Exception:
        pass

    # Try HTTP fallback to API (render)
    try:
        import os, json, urllib.request
        API_BASE = os.getenv("DATABASE_URL")  # intentionally fallback; change if you have NEXT env
        # If you have a running HTTP API, call /api/market/orderbook or /api/ledger/summary etc
        # Skipping remote call here to keep simple; return None if not available
    except Exception:
        pass
    return None


async def monitor_tp_sl(poll_interval: float = 2.0):
    """
    Background loop: looks for TP/SL triggers and executes them when conditions met.
    - Reads triggers from DB (models.TPTrigger)
    - Checks current market price (via price_feed.fetch_prices)
    - Executes simulated fills by calling execute_trade to close the position or create closing trade
    """
    print("⚡ monitor_tp_sl: started (poll_interval={}s)".format(poll_interval))
    while True:
        try:
            if SessionLocal and models:
                session = SessionLocal()
                try:
                    triggers = session.query(models.TPTrigger).filter_by(active=True).all()
                except Exception as e:
                    print("⚠️ monitor_tp_sl: DB query failed:", e)
                    triggers = []
                finally:
                    try:
                        session.close()
                    except Exception:
                        pass
            else:
                triggers = []

            # For each trigger, check market price
            for trig in triggers:
                symbol = trig.symbol
                tp = trig.tp
                sl = trig.sl
                try:
                    price = await _fetch_latest_price(symbol)
                except Exception:
                    price = None

                if price is None:
                    # can't evaluate now
                    continue

                triggered = None
                # check side and conditions (for long: TP if price >= tp; SL if price <= sl)
                if trig.side == "buy":
                    if tp is not None and price >= float(tp):
                        triggered = "tp"
                    if sl is not None and price <= float(sl):
                        triggered = "sl"
                else:
                    # short: TP when price <= tp, SL when price >= sl
                    if tp is not None and price <= float(tp):
                        triggered = "tp"
                    if sl is not None and price >= float(sl):
                        triggered = "sl"

                if triggered:
                    print(f"🎯 monitor_tp_sl: trigger {triggered} for trigger id={trig.id} symbol={symbol} price={price}")
                    # Execute a closing trade (side opposite of original)
                    close_side = "sell" if trig.side == "buy" else "buy"
                    # determine qty from position or trigger row (naive)
                    qty = getattr(trig, "qty", getattr(trig, "size", 1))
                    # call execute_trade to create fill and update positions
                    try:
                        await execute_trade(trig.user_id, symbol, close_side, price, qty, order_type="market")
                    except Exception as e:
                        print("❌ monitor_tp_sl: execute_trade failed:", e)
                    # mark trigger inactive
                    try:
                        session = SessionLocal() if SessionLocal else None
                        if session:
                            db_trig = session.query(models.TPTrigger).filter_by(id=trig.id).first()
                            if db_trig:
                                db_trig.active = False
                                session.add(db_trig)
                                session.commit()
                            try:
                                session.close()
                            except Exception:
                                pass
                    except Exception as e:
                        print("⚠️ monitor_tp_sl: couldn't deactivate trigger:", e)

            # sleep before next poll
            await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            print("monitor_tp_sl: cancelled, shutting down")
            break
        except Exception as e:
            print("monitor_tp_sl: unexpected error:", e)
            await asyncio.sleep(poll_interval)


# If you want a non-async wrapper to start monitor in background from main.py
def start_monitor_in_background(loop=None, poll_interval: float = 2.0):
    """
    Call this from your startup code:
      asyncio.create_task(monitor_tp_sl(2.0))
    or use this wrapper to schedule it on loop.
    """
    if not loop:
        loop = asyncio.get_event_loop()
    try:
        loop.create_task(monitor_tp_sl(poll_interval=poll_interval))
    except Exception as e:
        print("⚠️ trade_engine.start_monitor_in_background failed:", e)

    



