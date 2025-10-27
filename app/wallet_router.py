from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.wallet_service import WalletService
from app.ledger_service import LedgerService

router = APIRouter(prefix="/wallet", tags=["Wallet"])

@router.get("/{user_id}/{asset}")
def get_balance(user_id: int, asset: str, db: Session = Depends(get_db)):
    wallet = WalletService(db)
    try:
        balance = wallet.get_balance(user_id, asset)
        return {"user_id": user_id, "asset": asset.upper(), "balance": balance}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/deposit")
def deposit(user_id: int, asset: str, amount: float, db: Session = Depends(get_db)):
    wallet = WalletService(db)
    try:
        balance = wallet.deposit(user_id, asset, amount)
        return {"message": "Deposit successful", "balance": balance}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/withdraw")
def withdraw(user_id: int, asset: str, amount: float, db: Session = Depends(get_db)):
    wallet = WalletService(db)
    try:
        balance = wallet.withdraw(user_id, asset, amount)
        return {"message": "Withdrawal successful", "balance": balance}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{user_id}/ledger")
def get_ledger(user_id: int, db: Session = Depends(get_db)):
    ledger = LedgerService(db)
    entries = ledger.get_ledger(user_id)
    return {"user_id": user_id, "entries": entries}

