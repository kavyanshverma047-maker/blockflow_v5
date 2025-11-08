

# app/ledger_service.py
"""
Ledger Service – Blockflow Exchange (Render-ready)
Handles:
 - Ledger summaries
 - User-specific ledgers
 - Normalized transaction entries (Decimal-safe)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from decimal import Decimal
from typing import List, Dict, Any, Optional
from app.db import SessionLocal
from app.models import LedgerEntry
from app.dependencies import get_db

# ✅ Define FastAPI Router
router = APIRouter(prefix="/api/ledger", tags=["Ledger"])


# ✅ Normalize float/Decimal inputs safely
def _normalize_amount(amount) -> Decimal:
    if amount is None:
        return Decimal("0.0")
    if isinstance(amount, (int, float, str)):
        try:
            return Decimal(str(amount))
        except Exception:
            return Decimal("0.0")
    if isinstance(amount, Decimal):
        return amount
    return Decimal("0.0")


# ✅ Get complete ledger summary for Proof-of-Reserves
@router.get("/summary")
def get_summary(db: Session = Depends(get_db)) -> Dict[str, Any]:
    try:
        total_balance = db.query(func.sum(LedgerEntry.amount)).scalar() or 0
        total_entries = db.query(LedgerEntry).count()
        positive_tx = db.query(func.sum(func.case((LedgerEntry.amount > 0, LedgerEntry.amount), else_=0))).scalar() or 0
        negative_tx = db.query(func.sum(func.case((LedgerEntry.amount < 0, LedgerEntry.amount), else_=0))).scalar() or 0

        return {
            "status": "ok",
            "total_entries": total_entries,
            "total_balance": float(total_balance),
            "credits": float(positive_tx),
            "debits": float(negative_tx),
            "hash": f"por-{int(total_balance * 1000)}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ledger summary failed: {str(e)}")


# ✅ Get all ledger entries (admin/demo)
@router.get("/entries")
def get_all_entries(db: Session = Depends(get_db)) -> Dict[str, Any]:
    entries = db.query(LedgerEntry).limit(500).all()
    return {
        "count": len(entries),
        "entries": [
            {
                "id": e.id,
                "user_id": e.user_id,
                "asset": e.asset,
                "amount": float(_normalize_amount(e.amount)),
                "timestamp": str(e.timestamp),
                "type": e.type,
                "reference": e.reference or "-",
            }
            for e in entries
        ],
    }


# ✅ Get user-specific ledger (frontend: Wallet history)
@router.get("/user/{user_id}")
def get_user_ledger(user_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    entries = (
        db.query(LedgerEntry)
        .filter(LedgerEntry.user_id == user_id)
        .order_by(LedgerEntry.timestamp.desc())
        .limit(100)
        .all()
    )
    if not entries:
        raise HTTPException(status_code=404, detail=f"No ledger found for user {user_id}")
    return {
        "user_id": user_id,
        "count": len(entries),
        "entries": [
            {
                "asset": e.asset,
                "amount": float(_normalize_amount(e.amount)),
                "timestamp": str(e.timestamp),
                "type": e.type,
                "reference": e.reference or "-",
            }
            for e in entries
        ],
    }
