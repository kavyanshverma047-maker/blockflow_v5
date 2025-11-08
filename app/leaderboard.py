# app/leaderboard.py
import random
from datetime import datetime

def generate_leaderboard(n=10):
    traders = []
    for i in range(n):
        traders.append({
            "rank": i + 1,
            "username": f"Trader_{i+1}",
            "pnl_percent": round(random.uniform(-20, 85), 2),
            "win_rate": round(random.uniform(30, 90), 2),
            "last_trade": datetime.utcnow().isoformat()
        })
    return {"timestamp": datetime.utcnow().isoformat(), "top_traders": traders}
