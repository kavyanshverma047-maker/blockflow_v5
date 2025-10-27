# app/wallet_router.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, condecimal
from typing import Optional, List
from decimal import Decimal
from sqlalchemy.orm import Session

from app.wallet_service import WalletService
from app.main import get_db

router = APIRouter(prefix="/wallet", tags=["wallet"])
service = WalletService()


# Request schemas
class AmountRequest(BaseModel):
    user_id: int = Field(..., example=1)
    asset: str = Field(..., example="USDT")
    amount: condecimal(gt=0, decimal_places=8) = Field(..., example="10.5")
    meta: Optional[dict] = None


class TransferRequest(BaseModel):
    from_user_id: int = Field(..., example=1)
    to_user_id: int = Field(..., example=2)
    asset: str = Field(..., example="USDT")
    amount: condecimal(gt=0, decimal_places=8) = Field(..., example="1.0")
    meta: Optional[dict] = None


# Response schemas
class LedgerEntryOut(BaseModel):
    id: int
    user_id: int
    asset: str
    amount: Decimal
    balance_after: Optional[Decimal] = None
    type: Optional[str] = None
    meta: Optional[dict] = None
    created_at: Optional[str] = None

    class Config:
        orm_mode = True


@router.post("/deposit", response_model=LedgerEntryOut)
def deposit(req: AmountRequest, db: Session = Depends(get_db)):
    try:
        entry = service.deposit(db, req.user_id, req.asset, Decimal(req.amount), req.meta)
        db.commit()
        db.refresh(entry)
        return entry
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/withdraw", response_model=LedgerEntryOut)
def withdraw(req: AmountRequest, db: Session = Depends(get_db)):
    try:
        entry = service.withdraw(db, req.user_id, req.asset, Decimal(req.amount), req.meta)
        db.commit()
        db.refresh(entry)
        return entry
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/transfer")
def transfer(req: TransferRequest, db: Session = Depends(get_db)):
    try:
        result = service.transfer(db, req.from_user_id, req.to_user_id, req.asset, Decimal(req.amount), req.meta)
        db.commit()
        return {"status": "success", "result": result}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/ledger/{user_id}", response_model=List[LedgerEntryOut])
def get_ledger(user_id: int, db: Session = Depends(get_db)):
    try:
        entries = service.get_ledger(db, user_id)
        return entries
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/balance/{user_id}/{asset}")
def get_balance(user_id: int, asset: str, db: Session = Depends(get_db)):
    try:
        balance = service.get_balance(db, user_id, asset)
        return {"user_id": user_id, "asset": asset, "balance": str(balance)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
