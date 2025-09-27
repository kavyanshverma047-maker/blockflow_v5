from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
import uuid

from app import models
from app.database import Base, engine, SessionLocal
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------
# DB Initialization
# ---------------------------
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Blockflow Demo Exchange")

# Enable CORS (for frontend → backend calls)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # later replace "*" with your Vercel frontend URL for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# Pydantic Schemas
# ---------------------------

class TradeRequest(BaseModel):
    username: str
    side: str   # "buy" or "sell"
    pair: str = "BTC/USDT"
    amount: float
    price: float


class P2POrderRequest(BaseModel):
    username: str
    type: str        # "Buy" or "Sell"
    merchant: str
    price: float
    available: float
    limit_min: float
    limit_max: float
    payment_method: str


# ---------------------------
# Dependencies
# ---------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------
# Trading Endpoints
# ---------------------------

@app.post("/trade")
def place_trade(trade: TradeRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == trade.username).first()
    if not user:
        user = models.User(username=trade.username)
        db.add(user)
        db.commit()
        db.refresh(user)

    cost = trade.amount * trade.price

    if trade.side == "buy":
        if user.balance < cost:
            return {"error": "Insufficient balance"}
        user.balance -= cost
    elif trade.side == "sell":
        user.balance += cost

    new_trade = models.Trade(
        user_id=user.id,
        side=trade.side,
        pair=trade.pair,
        amount=trade.amount,
        price=trade.price,
    )
    db.add(new_trade)
    db.commit()
    db.refresh(new_trade)

    return {
        "message": "Trade executed",
        "balance": user.balance,
        "trade": {
            "id": new_trade.id,
            "side": new_trade.side,
            "amount": new_trade.amount,
            "price": new_trade.price,
            "pair": new_trade.pair,
        },
    }


@app.get("/portfolio/{username}")
def get_portfolio(username: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return {"error": "User not found"}
    return {"username": user.username, "balance": user.balance}


@app.get("/orders/{username}")
def get_orders(username: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return {"error": "User not found"}
    trades = db.query(models.Trade).filter(models.Trade.user_id == user.id).all()
    return [
        {"side": t.side, "amount": t.amount, "price": t.price, "pair": t.pair}
        for t in trades
    ]


@app.post("/reset/{username}")
def reset_balance(username: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        user = models.User(username=username, balance=1000000.0)
        db.add(user)
    else:
        user.balance = 1000000.0
    db.commit()
    return {"message": "Balance reset", "balance": user.balance}


# ---------------------------
# P2P Endpoints
# ---------------------------

@app.get("/p2p/orders")
def list_p2p_orders(db: Session = Depends(get_db)):
    return db.query(models.P2POrder).all()


@app.post("/p2p/orders")
def create_p2p_order(order: P2POrderRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == order.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Lock balance for Buy orders
    cost = order.available * order.price
    if order.type.lower() == "buy":
        if user.balance < cost:
            raise HTTPException(status_code=400, detail="Insufficient balance")
        user.balance -= cost

    new_order = models.P2POrder(
        id=str(uuid.uuid4()),
        user_id=user.id,
        type=order.type,
        merchant=order.merchant,
        price=order.price,
        available=order.available,
        limit_min=order.limit_min,
        limit_max=order.limit_max,
        payment_method=order.payment_method,
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    return new_order


@app.delete("/p2p/orders/{order_id}")
def delete_p2p_order(order_id: str, db: Session = Depends(get_db)):
    order = db.query(models.P2POrder).filter(models.P2POrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    db.delete(order)
    db.commit()
    return {"status": "deleted"}

