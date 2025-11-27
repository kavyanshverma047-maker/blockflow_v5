from fastapi import APIRouter
from datetime import datetime
import random

router = APIRouter(prefix="/api/system", tags=["system"])

EVENTS = [
    "Large withdrawal detected",
    "High-risk IP flagged",
    "Margin ratio under 5%",
    "Abnormal futures position",
    "API key abuse attempt",
    "KYC mismatch on document",
    "Unusual orderbook activity"
]

@router.get("/compliance-feed")
def compliance_feed():
    e = random.choice(EVENTS)
    from app.cache import cache_get, cache_set
    key='compliance'
    cached=cache_get(key)
    if cached: return cached
    data={
        "event": e,
        "category": random.choice(['low','medium','high']),
        "timestamp": datetime.utcnow().isoformat()
    }

    cache_set(key, data)
    return data
