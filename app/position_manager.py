# app/position_manager.py
"""
Position manager: create/update positions, compute PnL, close positions, etc.
This is intentionally minimal but production-structured:
 - Uses SQLAlchemy SessionLocal if available
 - Provides sync and async-friendly functions (async wrappers)
 - Exposes update_position which trade_engine imports & calls
"""

import time
from decimal import Decimal
from typing import Dict, Any, Optional

# try importing DB/session/models from app; fall back to stub behavior if not present
try:
    from app.db import SessionLocal
    from app import models
except Exception:
    SessionLocal = None
    models = None


def _now_ts() -> float:
    return time.time()


def _safe_decimal(v) -> float:
    try:
        return float(Decimal(v))
    except Exception:
        try:
            return float(v)
        except Exception:
            return 0.0


def create_or_update_position_db(session, user_id: int, symbol: str, side: str, qty: float, price: float) -> Dict[str, Any]:
    """
    Minimal database-backed position update:
      - If an open position for (user, symbol, side) exists -> average price / qty update
      - Else -> create new position record
    NOTE: adapt this to your real Position model fields.
    """
    # defensive: if no models, return stub
    if not models:
        return {
            "user_id": user_id, "symbol": symbol, "side": side,
            "qty": qty, "entry_price": price, "updated_at": _now_ts()
        }

    # Example behaviour (adapt to your actual models)
    # Try to find an existing open position for this user/symbol/side
    pos = session.query(models.Position).filter_by(user_id=user_id, symbol=symbol, side=side, closed=False).first()
    if pos:
        # compute new average entry price
        existing_qty = _safe_decimal(pos.qty)
        existing_price = _safe_decimal(pos.entry_price)
        new_qty = existing_qty + qty
        if new_qty <= 0:
            # closing or invalid: mark closed
            pos.closed = True
            session.add(pos)
            session.commit()
            return {"status": "closed", "id": pos.id}
        # weighted avg
        avg_price = ((existing_qty * existing_price) + (qty * price)) / new_qty
        pos.qty = new_qty
        pos.entry_price = avg_price
        pos.updated_at = _now_ts()
        session.add(pos)
        session.commit()
        return {"status": "updated", "id": pos.id, "qty": pos.qty, "entry_price": pos.entry_price}
    else:
        # create new position
        new_pos = models.Position(user_id=user_id, symbol=symbol, side=side, qty=qty, entry_price=price, created_at=_now_ts(), closed=False)
        session.add(new_pos)
        session.commit()
        return {"status": "created", "id": new_pos.id, "qty": new_pos.qty, "entry_price": new_pos.entry_price}


async def update_position(user_id: int, symbol: str, side: str, qty: float, price: float) -> Dict[str, Any]:
    """
    Public function used by trade_engine to update/create user positions after fills.
    Uses DB if available, otherwise returns a basic summary.
    """
    try:
        if SessionLocal and models:
            # run in a new DB session
            session = SessionLocal()
            try:
                res = create_or_update_position_db(session, user_id, symbol, side, qty, price)
                return {"ok": True, "result": res}
            finally:
                try:
                    session.close()
                except Exception:
                    pass
        else:
            # DB not available in current runtime — fallback
            print("⚠️ position_manager: DB not available — returning stub update_position result")
            return {"ok": True, "result": {"user_id": user_id, "symbol": symbol, "side": side, "qty": qty, "entry_price": price}}
    except Exception as e:
        print("❌ position_manager.update_position error:", e)
        return {"ok": False, "error": str(e)}


# Optional helper to compute PnL given current price
def compute_unrealized_pnl(entry_price: float, current_price: float, qty: float, side: str) -> float:
    entry = _safe_decimal(entry_price)
    cur = _safe_decimal(current_price)
    q = _safe_decimal(qty)
    if q == 0:
        return 0.0
    if side == "buy":
        pnl = (cur - entry) * q
    else:
        pnl = (entry - cur) * q
    return float(pnl)
