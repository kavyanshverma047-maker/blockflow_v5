from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db import SessionLocal
import random
from datetime import datetime

router = APIRouter(prefix="/api/wallet", tags=["wallet"])

@router.get("/balance/{username}")
def get_balance(username: str):
    """Fetch wallet balance for user or return demo simulated balances."""
    db: Session = SessionLocal()
    try:
        query = text("""
            SELECT asset, SUM(amount) as balance
            FROM wallet_entries
            WHERE username = :username
            GROUP BY asset
        """)
        result = db.execute(query, {"username": username}).fetchall()

        # ✅ Fallback: if no data in DB, show simulated demo balances
        if not result or len(result) == 0:
            demo_assets = ["USDT", "BTC", "ETH", "SOL", "BNB", "MATIC"]
            balances = []
            for asset in demo_assets:
                # Simulate balance values that fluctuate slightly
                base = {
                    "USDT": random.uniform(500, 20000),
                    "BTC": random.uniform(0.05, 2),
                    "ETH": random.uniform(0.5, 20),
                    "SOL": random.uniform(10, 500),
                    "BNB": random.uniform(1, 50),
                    "MATIC": random.uniform(100, 20000),
                }[asset]
                fluctuation = base * random.uniform(-0.02, 0.02)
                balances.append({
                    "asset": asset,
                    "balance": round(base + fluctuation, 4),
                    "updated_at": datetime.utcnow().isoformat()
                })
            return balances

        # ✅ Otherwise return real data from DB
        return [{"asset": row[0], "balance": float(row[1])} for row in result]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/ledger/{username}")
def get_ledger(username: str):
    """Fetch ledger for a given username or return simulated transactions."""
    db: Session = SessionLocal()
    try:
        result = db.execute(
            text("SELECT id, pair, side, price, amount, timestamp FROM spot_trades WHERE username = :username"),
            {"username": username},
        ).fetchall()

        if not result:
            # Demo ledger generator
            pairs = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
            sides = ["buy", "sell"]
            ledger = [
                {
                    "pair": random.choice(pairs),
                    "side": random.choice(sides),
                    "price": round(random.uniform(100, 70000), 2),
                    "amount": round(random.uniform(0.01, 1.0), 4),
                    "timestamp": datetime.utcnow().isoformat(),
                }
                for _ in range(20)
            ]
            return ledger

        return [
            {
                "pair": row[1],
                "side": row[2],
                "price": float(row[3]),
                "amount": float(row[4]),
                "timestamp": str(row[5]),
            }
            for row in result
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
