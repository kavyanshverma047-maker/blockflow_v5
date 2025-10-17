# app/position_manager.py
from datetime import datetime
from typing import Dict, Any
import random

# shared in-memory position data
positions: Dict[str, Any] = {}

def open_position(user_id: str, symbol: str, side: str, entry_price: float, leverage: int, qty: float):
    pos_id = f"{user_id}_{symbol}_{int(datetime.utcnow().timestamp())}"
    positions[pos_id] = {
        "id": pos_id,
        "user_id": user_id,
        "symbol": symbol,
        "side": side,
        "entry": entry_price,
        "leverage": leverage,
        "qty": qty,
        "opened_at": datetime.utcnow().isoformat(),
        "closed": False,
        "exit_price": None,
        "pnl": 0.0
    }
    return positions[pos_id]

def update_pnl(symbol: str, price: float):
    for pid, p in positions.items():
        if p["symbol"] == symbol and not p["closed"]:
            diff = (price - p["entry"]) if p["side"] == "long" else (p["entry"] - price)
            p["pnl"] = round(diff * p["qty"] * p["leverage"], 4)

def close_position(pos_id: str, price: float):
    if pos_id in positions:
        p = positions[pos_id]
        p["closed"] = True
        p["exit_price"] = price
        p["closed_at"] = datetime.utcnow().isoformat()
        return p
    return None

def get_active_positions():
    return [p for p in positions.values() if not p["closed"]]
async def update_position(symbol: str, user_id: int, side: str, qty: float, price: float):
    """
    Update user's position after trade execution.
    """
    print(f"📊 Updating position for {symbol} user={user_id} side={side}")
    # Placeholder logic
    return {"symbol": symbol, "user": user_id, "side": side, "qty": qty, "price": price}

