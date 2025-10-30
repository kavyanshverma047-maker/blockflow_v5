
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db  # ✅ YE LINE CHANGE KARO

# Safe imports for models
try:
    from app.models import User, SpotTrade, MarginTrade, FuturesUsdmTrade, FuturesCoinmTrade
except ImportError:
    from app.models import User
    SpotTrade = None
    MarginTrade = None
    FuturesUsdmTrade = None
    FuturesCoinmTrade = None

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
        total_futures = db.query(FuturesUsdmTrade).count() if FuturesUsdmTrade else 0
        total_coinm = db.query(FuturesCoinmTrade).count() if FuturesCoinmTrade else 0

        return {
            "total_users": total_users,
            "spot_trades": total_spot,
            "margin_trades": total_margin,
            "futures_usdm_trades": total_futures,
            "futures_coinm_trades": total_coinm,
            "total_volume": total_spot + total_margin + total_futures + total_coinm
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## Step 3: DONE! 🎉

**Bas itna hi!** Main.py ko touch bhi mat karna. 

Ye 2 files banao/update karo:
1. ✅ `app/db.py` - NEW file
2. ✅ `app/admin_router.py` - Sirf pehli line change (`from app.db import get_db`)

**Deploy karo Render pe aur check karo:**
```
https://blockflow-v5-1.onrender.com/health
https://blockflow-v5-1.onrender.com/api/admin/stats
