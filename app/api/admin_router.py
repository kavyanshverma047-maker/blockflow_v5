
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User, LedgerEntry, FuturesUsdMTrade, SpotTrade

# ✅ Use "router" as the export name (FastAPI expects this)
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
        total_spot_trades = db.query(SpotTrade).count()
        total_futures_trades = db.query(FuturesUsdMTrade).count()
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
