import asyncio
import random
from datetime import datetime

# shared global state for metrics
metrics_data = {
    "users_simulated": 10200000,
    "demo_trades_executed": 91600000,
    "transactions_secured": 12400000000,
    "active_markets": 320,
    "tps": 1400,
    "latency_ms": 12.0,
    "last_update": datetime.utcnow().isoformat(),
}

async def simulate_metrics():
    """Continuously updates metrics_data every few seconds."""
    while True:
        # simulate realistic fluctuations
        metrics_data["users_simulated"] += random.randint(50, 200)
        metrics_data["demo_trades_executed"] += random.randint(5000, 10000)
        metrics_data["transactions_secured"] += random.randint(100000, 200000)
        metrics_data["tps"] = round(random.uniform(1350, 1450), 2)
        metrics_data["latency_ms"] = round(random.uniform(11.5, 12.8), 2)
        metrics_data["last_update"] = datetime.utcnow().isoformat()
        await asyncio.sleep(3)
