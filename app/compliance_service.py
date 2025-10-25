from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
import random
from app.db import get_db
from app.models import SpotTrade

router = APIRouter(prefix="/api", tags=["Compliance"])

@router.get("/regulator")
def regulator_dashboard(db: Session = Depends(get_db)):
    total_tds = db.query(SpotTrade).count() * 0.01
    ratio = round(random.uniform(0.94, 1.06), 3)
    return {
        "tds_collected_inr": round(total_tds, 2),
        "collateral_ratio": ratio,
        "aml_alerts": [{"user":"demo_trader_12","reason":"suspicious volume"}],
        "node_health": "Good",
        "uptime": "99.98%",
        "last_updated": datetime.utcnow().isoformat()
    }

@router.get("/infrastructure")
def infrastructure():
    return {
        "nodes": [
            {"region": "Mumbai", "uptime": "99.97%", "latency": 11.8},
            {"region": "Singapore", "uptime": "99.99%", "latency": 12.2},
            {"region": "London", "uptime": "99.95%", "latency": 13.0},
        ],
        "system_load": random.randint(40, 70),
        "db_latency_ms": round(random.uniform(10, 13), 2)
    }
