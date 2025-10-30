# app/admin_router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db

try:
    from app.models import User, SpotTrade, MarginTrade, FuturesUsdmTrade, FuturesCoinmTrade, OptionsTrade, P2POrder
except ImportError:
    from app.models import User
    SpotTrade = None
    MarginTrade = None
    FuturesUsdmTrade = None
    FuturesCoinmTrade = None
    OptionsTrade = None
    P2POrder = None

router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)

@router.get("/stats")
def get_admin_stats(db: Session = Depends(get_db)):
    try:
        total_users = db.query(User).count()
        total_spot = db.query(SpotTrade).count() if SpotTrade else 0
        total_margin = db.query(MarginTrade).count() if MarginTrade else 0
        total_futures_usdm = db.query(FuturesUsdmTrade).count() if FuturesUsdmTrade else 0
        total_futures_coinm = db.query(FuturesCoinmTrade).count() if FuturesCoinmTrade else 0
        total_options = db.query(OptionsTrade).count() if OptionsTrade else 0
        total_p2p = db.query(P2POrder).count() if P2POrder else 0

        return {
            "total_users": total_users,
            "spot_trades": total_spot,
            "margin_trades": total_margin,
            "futures_usdm_trades": total_futures_usdm,
            "futures_coinm_trades": total_futures_coinm,
            "options_trades": total_options,
            "p2p_orders": total_p2p,
            "total_volume": total_spot + total_margin + total_futures_usdm + total_futures_coinm + total_options
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
def admin_health():
    return {"status": "ok", "service": "admin_router"}
