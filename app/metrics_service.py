from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from datetime import datetime
import random, asyncio, json

from app.db import get_db
from app.models import User, SpotTrade, FuturesUsdmTrade, FuturesCoinmTrade

router = APIRouter(prefix="/api", tags=["Metrics"])

def get_metrics(db: Session):
    users = db.query(User).count()
    trades = db.query(SpotTrade).count() + db.query(FuturesUsdmTrade).count() + db.query(FuturesCoinmTrade).count()
    ledger_entries = trades * 4
    return {
        "users_simulated": users,
        "demo_trades_executed": trades,
        "transactions_secured": ledger_entries,
        "active_markets": 320,
        "tps": random.randint(1300, 1450),
        "latency_ms": round(random.uniform(10.8, 12.4), 2),
        "updated_at": datetime.utcnow().isoformat()
    }

@router.get("/metrics")
def metrics(db: Session = Depends(get_db)):
    return get_metrics(db)

@router.websocket("/ws/metrics")
async def metrics_ws(ws: WebSocket, db: Session = Depends(get_db)):
    await ws.accept()
    try:
        while True:
            await ws.send_text(json.dumps(get_metrics(db)))
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        pass
