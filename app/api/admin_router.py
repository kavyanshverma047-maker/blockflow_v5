from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import traceback
from datetime import datetime

try:
    from app.main import get_db
except ImportError:
    from app.db import get_db

try:
    from app.models import (
        User, SpotTrade, MarginTrade,
        FuturesUsdmTrade, FuturesCoinmTrade,
        OptionsTrade, P2POrder
    )
except ImportError:
    User = SpotTrade = MarginTrade = FuturesUsdmTrade = FuturesCoinmTrade = OptionsTrade = P2POrder = None

router = APIRouter(tags=["Admin"])

def safe_count(db: Session, model):
    """Safely count records from a model with error handling."""
    if model is None:
        return 0
    try:
        return db.query(model).count()
    except Exception as e:
        print(f"[safe_count] Error counting {model.__name__}: {e}")
        return 0

# ✅ HEALTH ENDPOINT
@router.get("/health")
def admin_health():
    """Simple health check for admin router"""
    return {
        "status": "ok",
        "service": "admin_router",
        "version": "2.0-Brahmastra",
        "timestamp": datetime.utcnow().isoformat()
    }

# ✅ STATS ENDPOINT
@router.get("/stats")
def get_admin_stats(db: Session = Depends(get_db)):
    """Aggregate system-wide trade and user statistics"""
    try:
        total_users = safe_count(db, User)
        total_spot = safe_count(db, SpotTrade)
        total_margin = safe_count(db, MarginTrade)
        total_futures_usdm = safe_count(db, FuturesUsdmTrade)
        total_futures_coinm = safe_count(db, FuturesCoinmTrade)
        total_options = safe_count(db, OptionsTrade)
        total_p2p = safe_count(db, P2POrder)

        total_volume = (
            total_spot + total_margin +
            total_futures_usdm + total_futures_coinm +
            total_options
        )

        return {
            "status": "ok",
            "users": total_users,
            "spot_trades": total_spot,
            "margin_trades": total_margin,
            "futures_usdm_trades": total_futures_usdm,
            "futures_coinm_trades": total_futures_coinm,
            "options_trades": total_options,
            "p2p_orders": total_p2p,
            "total_volume": total_volume,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"[Admin Stats Error]: {error_trace}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch admin stats: {str(e)}")

# ✅ SEED STATUS ENDPOINT
@router.get("/seed-status")
def seed_status(db: Session = Depends(get_db)):
    """Check if demo or live data is seeded in DB"""
    try:
        user_count = safe_count(db, User)
        trade_count = safe_count(db, SpotTrade)

        return {
            "seeded": user_count > 0,
            "users": user_count,
            "trades": trade_count,
            "needs_seed": user_count == 0,
            "checked_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "seeded": False,
            "error": str(e),
            "checked_at": datetime.utcnow().isoformat()
        }
