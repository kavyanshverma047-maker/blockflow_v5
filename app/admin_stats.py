from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import math, random
from app.dependencies import get_db
from app.models import User

router = APIRouter(prefix="/api/admin", tags=["admin-stats"])

@router.get("/stats")
async def get_admin_stats(db: Session = Depends(get_db)):
    """Hybrid Real + Simulated Investor Metrics"""
    try:
        total_users = db.query(User).count()
        trade_multiplier = math.log1p(total_users / 100000)

        spot_trades = int(total_users * trade_multiplier * random.uniform(4.0, 6.0))
        margin_trades = int(total_users * trade_multiplier * random.uniform(0.6, 1.2))
        futures_usdm_trades = int(total_users * trade_multiplier * random.uniform(0.4, 0.9))
        futures_coinm_trades = int(total_users * trade_multiplier * random.uniform(0.2, 0.5))
        options_trades = int(total_users * trade_multiplier * random.uniform(0.1, 0.3))
        p2p_orders = int(total_users * trade_multiplier * random.uniform(0.05, 0.15))

        avg_trade_value = random.uniform(500, 1200)
        total_volume_usd = (
            (spot_trades + margin_trades + futures_usdm_trades) * avg_trade_value / 1_000_000_000
        )
        total_pnl_usd = round(total_volume_usd * random.uniform(-0.03, 0.06), 2)
        secured_transactions = (
            spot_trades + margin_trades + futures_usdm_trades + futures_coinm_trades
        )

        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        return {
            "status": "ok",
            "demo_scale": {
                "total_users": f"{total_users:,}",
                "spot_trades": f"{spot_trades:,}",
                "margin_trades": f"{margin_trades:,}",
                "futures_usdm_trades": f"{futures_usdm_trades:,}",
                "futures_coinm_trades": f"{futures_coinm_trades:,}",
                "options_trades": f"{options_trades:,}",
                "p2p_orders": f"{p2p_orders:,}",
                "secured_transactions": f"{secured_transactions:,}",
                "total_volume_usd_billion": f"{total_volume_usd:.2f}",
                "total_pnl_usd_billion": f"{total_pnl_usd:.2f}",
            },
            "timestamp": now,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
