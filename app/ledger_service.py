# app/ledger_service.py
from datetime import datetime
import random, uuid

ledger = []

def log_trade(symbol: str, side: str, amount: float, price: float):
    """Simulate trade entry for internal audit log."""
    trade = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "symbol": symbol,
        "side": side,
        "amount": amount,
        "price": price,
        "value_usd": round(amount * price, 2),
        "tds": round(amount * price * 0.001, 2),
        "gst": round(amount * price * 0.0005, 2),
    }
    ledger.append(trade)
    if len(ledger) > 1000:  # limit size
        ledger.pop(0)
    return trade

def get_recent_trades():
    """Return last N trade logs."""
    return ledger[-20:]
