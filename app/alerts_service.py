# app/alerts_service.py
from datetime import datetime
import random

alerts = []

def simulate_alerts():
    possible = [
        "High liquidation volume detected",
        "Funding rate spike > 0.05%",
        "TDS collection lag detected",
        "Liquidity coverage below 1.0",
        "Anomalous trade pattern in BTC/USDT",
    ]
    new_alert = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "message": random.choice(possible),
        "severity": random.choice(["Low", "Medium", "High"]),
    }
    alerts.append(new_alert)
    if len(alerts) > 10:
        alerts.pop(0)
    return alerts
