# app/pnl_engine.py
from datetime import datetime
import random

pnl_state = {
    "total_realized_pnl": 0.0,
    "total_unrealized_pnl": 0.0,
    "avg_pnl_per_user": 0.0,
    "winning_traders": 0,
    "losing_traders": 0,
    "last_update": None,
}

def simulate_pnl_cycle():
    """Simulate portfolio profit/loss movement."""
    global pnl_state
    change = random.uniform(-0.002, 0.003)  # -0.2% to +0.3%
    pnl_state["total_realized_pnl"] += round(random.uniform(-10000, 20000), 2)
    pnl_state["total_unrealized_pnl"] += round(random.uniform(-8000, 16000), 2)
    pnl_state["avg_pnl_per_user"] = round(random.uniform(-2.5, 2.5), 3)
    pnl_state["winning_traders"] = random.randint(4000000, 5200000)
    pnl_state["losing_traders"] = 10_000_000 - pnl_state["winning_traders"]
    pnl_state["last_update"] = datetime.utcnow().isoformat() + "Z"
    return pnl_state
