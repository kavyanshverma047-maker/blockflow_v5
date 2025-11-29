from fastapi import APIRouter
from datetime import datetime
router = APIRouter(prefix="/health", tags=["Health"])
_start = datetime.utcnow()
_engine = None
_ws = None
def set_deps(engine, ws): 
    global _engine, _ws
    _engine=engine; _ws=ws
@router.get("")
async def health():
    return {"status":"healthy","timestamp":datetime.utcnow().isoformat(),"uptime_seconds":(datetime.utcnow()-_start).total_seconds(),"market_engine": _engine.health_check() if _engine else {}, "websocket_manager": _ws.get_stats() if _ws else {}}
@router.get("/live")
async def live():
    return {"status":"alive","timestamp":datetime.utcnow().isoformat()}
@router.get("/ready")
async def ready():
    ok = True
    checks = {}
    if _engine:
        try:
            snap = _engine.get_snapshot("BTCUSDT")
            checks["market_engine"] = {"status":"ready","has_orderbook": len(snap["orderbook"]["bids"])>0}
        except Exception as e:
            checks["market_engine"] = {"status":"not_ready","error":str(e)}; ok=False
    else:
        checks["market_engine"]={"status":"not_initialized"}; ok=False
    if _ws:
        checks["websocket_manager"]={"status":"ready"}
    else:
        checks["websocket_manager"]={"status":"not_initialized"}; ok=False
    return {"status": "ready" if ok else "not_ready", "checks":checks}
