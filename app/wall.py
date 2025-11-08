from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from decimal import Decimal
from app import models, database

router = APIRouter(prefix="/wall", tags=["Wallet / BuyCrypto"])

# ---------- Request Models ----------
class DepositRequest(BaseModel):
    username: str
    amount: float
    method: str   # "p2p", "fiat", "onchain"

class WithdrawRequest(BaseModel):
    username: str
    amount: float
    address: str

class SpotBuyRequest(BaseModel):
    username: str
    base: str       # e.g. "BTC"
    quote: str      # e.g. "USDT"
    amount: float   # how much quote to spend
    price: float    # mock price for trade


# ---------- Deposit ----------
@router.post("/deposit")
def deposit(req: DepositRequest, db: Session = Depends(database.SessionLocal)):
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid deposit amount")

    user = db.query(models.User).filter(models.User.username == req.username).first()
    if not user:
        user = models.User(username=req.username, balance=0.0)
        db.add(user)
        db.commit()
        db.refresh(user)

    user.balance += req.amount
    db.commit()

    return {
        "status": "success",
        "username": user.username,
        "balance": user.balance,
        "method": req.method
    }


# ---------- Withdraw ----------
@router.post("/withdraw")
def withdraw(req: WithdrawRequest, db: Session = Depends(database.SessionLocal)):
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid withdrawal amount")

    user = db.query(models.User).filter(models.User.username == req.username).first()
    if not user or user.balance < req.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    user.balance -= req.amount
    db.commit()

    return {
        "status": "success",
        "username": user.username,
        "balance": user.balance,
        "withdrawn": req.amount,
        "to_address": req.address
    }


# ---------- Spot Buy ----------
@router.post("/spot")
def spot_buy(req: SpotBuyRequest, db: Session = Depends(database.SessionLocal)):
    if req.amount <= 0 or req.price <= 0:
        raise HTTPException(status_code=400, detail="Invalid trade parameters")

    user = db.query(models.User).filter(models.User.username == req.username).first()
    if not user or user.balance < req.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    # Deduct quote currency (USDT assumed)
    user.balance -= req.amount
    db.commit()

    # Record trade (mock execution)
    trade = models.Trade(
        user_id=user.id,
        side="buy",
        pair=f"{req.base}/{req.quote}",
        amount=req.amount / req.price,  # crypto quantity
        price=req.price
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)

    return {
        "status": "success",
        "trade_id": trade.id,
        "pair": trade.pair,
        "amount": trade.amount,
        "price": trade.price,
        "balance": user.balance
    }
# ---------- Dummy Endpoints for Prototype ----------

@router.post("/p2p")
def p2p_order(req: DepositRequest):
    return {
        "status": "success",
        "method": "p2p",
        "message": f"P2P order placed for {req.amount} USDT by {req.username}"
    }

@router.post("/fiat")
def fiat_deposit(req: DepositRequest):
    return {
        "status": "success",
        "method": "fiat",
        "message": f"Fiat deposit of {req.amount} initiated for {req.username}"
    }

@router.post("/onchain")
def onchain_deposit(req: DepositRequest):
    return {
        "status": "pending",
        "method": "onchain",
        "message": f"Blockchain tx pending for {req.amount} USDT by {req.username}"
    }

