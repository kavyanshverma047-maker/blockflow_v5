
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db

# Safe imports for models
try:
    from app.models import User, LedgerEntry, FuturesUsdMTrade, SpotTrade
except ImportError:
    from app.models import User, LedgerEntry
    FuturesUsdMTrade = None
    SpotTrade = None

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    include_in_schema=False
)

@router.get("/stats")
def get_admin_stats(db: Session = Depends(get_db)):
    try:
        total_users = db.query(User).count()
        total_ledger = db.query(LedgerEntry).count()

        # ✅ Handle missing models gracefully
        total_spot_trades = db.query(SpotTrade).count() if SpotTrade else 0
        total_futures_trades = db.query(FuturesUsdMTrade).count() if FuturesUsdMTrade else 0

        total_volume = db.query(LedgerEntry).filter(LedgerEntry.type == "TRADE").count()

        return {
            "total_users": total_users,
            "ledger_entries": total_ledger,
            "spot_trades": total_spot_trades,
            "futures_trades": total_futures_trades,
            "total_volume": total_volume,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Admin stats fetch failed: {str(e)}")
