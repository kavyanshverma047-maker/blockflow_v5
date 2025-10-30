# app/admin_router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
import traceback

try:
    from app.models import (
        User, SpotTrade, MarginTrade, 
        FuturesUsdmTrade, FuturesCoinmTrade, 
        OptionsTrade, P2POrder
    )
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

def safe_count(db: Session, model):
    """Safely count records from a model with error handling"""
    if model is None:
        return 0
    try:
        return db.query(model).count()
    except Exception as e:
        print(f"Error counting {model.__name__ if model else 'unknown'}: {e}")
        return 0

@router.get("/stats")
def get_admin_stats(db: Session = Depends(get_db)):
    """Get admin statistics with safe error handling"""
    try:
        # Count users (this should always work)
        total_users = safe_count(db, User)
        
        # Count trades with safe handling
        total_spot = safe_count(db, SpotTrade)
        total_margin = safe_count(db, MarginTrade)
        total_futures_usdm = safe_count(db, FuturesUsdmTrade)
        total_futures_coinm = safe_count(db, FuturesCoinmTrade)
        total_options = safe_count(db, OptionsTrade)
        total_p2p = safe_count(db, P2POrder)
        
        # Calculate total volume
        total_volume = (
            total_spot + 
            total_margin + 
            total_futures_usdm + 
            total_futures_coinm + 
            total_options
        )

        return {
            "status": "ok",
            "total_users": total_users,
            "spot_trades": total_spot,
            "margin_trades": total_margin,
            "futures_usdm_trades": total_futures_usdm,
            "futures_coinm_trades": total_futures_coinm,
            "options_trades": total_options,
            "p2p_orders": total_p2p,
            "total_volume": total_volume,
            "timestamp": "2025-10-31"
        }
        
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"Admin stats error: {error_trace}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to fetch admin stats: {str(e)}"
        )

@router.get("/health")
def admin_health():
    """Simple health check for admin router"""
    return {
        "status": "ok", 
        "service": "admin_router",
        "version": "2.0"
    }

@router.get("/seed-status")
def seed_status(db: Session = Depends(get_db)):
    """Check if database is seeded with data"""
    try:
        user_count = safe_count(db, User)
        trade_count = safe_count(db, SpotTrade)
        
        return {
            "seeded": user_count > 0,
            "users": user_count,
            "trades": trade_count,
            "needs_seed": user_count == 0
        }
    except Exception as e:
        return {
            "seeded": False,
            "error": str(e)
        }
