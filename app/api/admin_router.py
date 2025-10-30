# app/admin_router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
import traceback

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
        
        # Safe counting with error handling
        def safe_count(model):
            try:
                return db.query(model).count() if model else 0
            except Exception as e:
                print(f"Error counting {model}: {e}")
                return 0
        
        total_spot = safe_count(SpotTrade)
        total_margin = safe_count(MarginTrade)
        total_futures_usdm = safe_count(FuturesUsdmTrade)
        total_futures_coinm = safe_count(FuturesCoinmTrade)
        total_options = safe_count(OptionsTrade)
        total_p2p = safe_count(P2POrder)

        return {
            "status": "ok",
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
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
def admin_health():
    return {"status": "ok", "service": "admin_router"}
