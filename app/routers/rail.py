from fastapi import APIRouter
from datetime import datetime
import random

router = APIRouter(prefix="/api/system", tags=["system"])

@router.get("/rail")
def rail_status():
    from app.cache import cache_get, cache_set
    key='rail'
    cached=cache_get(key)
    if cached: return cached
    data={
        "latency_ms": random.randint(29, 45),
        "settlement_ms": random.randint(80, 120),
        "integrity_score": round(random.uniform(98.5, 99.9), 2),
        "status": "operational",
        "time": datetime.utcnow().isoformat()
    }

    cache_set(key, data)
    return data
