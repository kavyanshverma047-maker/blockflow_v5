from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel

import app.models as models
import app.database as database

# Initialize DB
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Blockflow Demo Exchange")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 🔥 later restrict to your Vercel domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic schemas
class TradeRequest(BaseModel):
    username: str
    side: str   # "buy" or "sell"
    pair: str = "BTC/USDT"
    amount: float
    price: float


# Place a trade
@app.post("/trade")
def place_trade(trade: TradeRequest, db: Session = Depends(database.SessionLocal)):
    user = db.query(models.User).filter(models.User.username == trade.username).first()
    if not user:
        user = models.User(username=trade.username, balance=1_000_000.0)
        db.add(user)
        db.commit()
        db.refresh(user)

    cost = trade.amount * trade.price

    if trade.side == "buy":
        if user.balance < cost:
            raise HTTPException(status_code=400, detail="Insufficient balance")
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


# Get portfolio
@app.get("/portfolio/{username}")
def get_portfolio(username: str, db: Session = Depends(database.SessionLocal)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"username": user.username, "balance": user.balance}


# Get orders
@app.get("/orders/{username}")
def get_orders(username: str, db: Session = Depends(database.SessionLocal)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    trades = db.query(models.Trade).filter(models.Trade.user_id == user.id).all()
    return [
        {"id": t.id, "side": t.side, "amount": t.amount, "price": t.price, "pair": t.pair}
        for t in trades
    ]


# Reset balance
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

   

