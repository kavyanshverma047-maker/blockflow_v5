from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from . import models, database

# ✅ init database
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Blockflow v5 Ledger Demo + Trading API")

# -------------------------------
# 📌 Pydantic schemas
# -------------------------------

class TradeRequest(BaseModel):
    username: str
    side: str    # "buy" or "sell"
    pair: str = "BTC/USDT"
    amount: float
    price: float


# -------------------------------
# ✅ Existing Ledger Endpoints
# (Keep your /deposit, /reserve, /release, etc. here)
# -------------------------------

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/home")
def home():
    return {"message": "Welcome to Blockflow v5 Ledger Demo"}

# (⚡ NOTE: keep your existing /deposit, /reserve, /release, /settle_trade, /balances, /markets here.
# I’m not rewriting them now since they’re already working on Render.
# Just make sure you don’t delete them when pasting this new code.)
 

# -------------------------------
# ✅ New Trading Endpoints
# -------------------------------

@app.post("/trade")
def place_trade(trade: TradeRequest, db: Session = Depends(database.SessionLocal)):
    # get or create user
    user = db.query(models.User).filter(models.User.username == trade.username).first()
    if not user:
        user = models.User(username=trade.username)
        db.add(user)
        db.commit()
        db.refresh(user)

    cost = trade.amount * trade.price

    if trade.side.lower() == "buy":
        if user.balance < cost:
            return {"error": "Insufficient balance", "balance": user.balance}
        user.balance -= cost
    elif trade.side.lower() == "sell":
        user.balance += cost
    else:
        return {"error": "Invalid trade side", "balance": user.balance}

    new_trade = models.Trade(
        user_id=user.id,
        side=trade.side.lower(),
        pair=trade.pair,
        amount=trade.amount,
        price=trade.price,
        timestamp=datetime.utcnow()
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
            "pair": new_trade.pair,
            "amount": new_trade.amount,
            "price": new_trade.price,
            "timestamp": new_trade.timestamp.isoformat()
        }
    }


@app.get("/portfolio/{username}")
def get_portfolio(username: str, db: Session = Depends(database.SessionLocal)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return {"error": "User not found"}
    return {"username": user.username, "balance": user.balance}


@app.get("/orders/{username}")
def get_orders(username: str, db: Session = Depends(database.SessionLocal)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return {"error": "User not found"}
    trades = db.query(models.Trade).filter(models.Trade.user_id == user.id).order_by(models.Trade.timestamp.desc()).all()
    return [
        {
            "id": t.id,
            "side": t.side,
            "pair": t.pair,
            "amount": t.amount,
            "price": t.price,
            "timestamp": t.timestamp.isoformat()
        }
        for t in trades
    ]


@app.post("/reset/{username}")
def reset_balance(username: str, db: Session = Depends(database.SessionLocal)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        user = models.User(username=username, balance=1_000_000.0)
        db.add(user)
    else:
        user.balance = 1_000_000.0
    db.commit()
    return {"message": "Balance reset", "balance": user.balance}


   

