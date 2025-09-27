from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import uuid

from app import models
from app.database import Base, engine, SessionLocal
from fastapi.middleware.cors import CORSMiddleware

# -----------------------------------------------------
# Create FastAPI app
# -----------------------------------------------------
app = FastAPI(title="Blockflow Prototype Exchange")

# -----------------------------------------------------
# Initialize database tables
# -----------------------------------------------------
models.Base.metadata.create_all(bind=engine)

# -----------------------------------------------------
# Enable CORS (for frontend integration)
# -----------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ in prod, restrict to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------
# DB Session Dependency
# -----------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -----------------------------------------------------
# Schemas
# -----------------------------------------------------
class UserCreate(BaseModel):
    username: str
    email: Optional[str] = None

class P2POrderRequest(BaseModel):
    username: str
    type: str          # "Buy" or "Sell"
    merchant: str
    price: float
    available: float
    limit_min: float
    limit_max: float
    payment_method: str

class TradeRequest(BaseModel):  # for Spot / Futures / Margin prototypes
    username: str
    side: str        # "buy" or "sell"
    pair: str        # e.g. "BTC/USDT"
    amount: float
    price: float

# -----------------------------------------------------
# Root healthcheck
# -----------------------------------------------------
@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "Blockflow API",
        "message": "Backend is running successfully 🚀"
    }

# -----------------------------------------------------
# USERS
# -----------------------------------------------------
@app.post("/users")
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    new_user = models.User(username=user.username, email=user.email)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.get("/users")
def list_users(db: Session = Depends(get_db)):
    return db.query(models.User).all()

# -----------------------------------------------------
# P2P ORDERS
# -----------------------------------------------------
@app.get("/p2p/orders")
def list_p2p_orders(db: Session = Depends(get_db)):
    return db.query(models.P2POrder).all()

@app.post("/p2p/orders")
def create_p2p_order(order: P2POrderRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == order.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Cost check only for Buy orders
    cost = order.available * order.price
    if order.type.lower() == "buy":
        if user.balance < cost:
            raise HTTPException(status_code=400, detail="Insufficient balance")
        user.balance -= cost

    new_order = models.P2POrder(
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
def delete_p2p_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.P2POrder).filter(models.P2POrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    db.delete(order)
    db.commit()
    return {"message": "Order deleted successfully"}

# -----------------------------------------------------
# SPOT TRADING (prototype)
# -----------------------------------------------------
@app.post("/spot/trade")
def place_spot_trade(trade: TradeRequest, db: Session = Depends(get_db)):
    # For prototype: just echo the trade request
    return {
        "message": "Spot trade placed successfully (prototype)",
        "trade": trade.dict()
    }

@app.get("/spot")
def get_spot():
    return {"message": "Spot trading endpoint (prototype)"}

# -----------------------------------------------------
# FUTURES TRADING (prototype)
# -----------------------------------------------------
@app.post("/futures/trade")
def place_futures_trade(trade: TradeRequest):
    return {
        "message": "Futures trade placed successfully (prototype)",
        "trade": trade.dict()
    }

@app.get("/futures")
def get_futures():
    return {"message": "Futures trading endpoint (prototype)"}

# -----------------------------------------------------
# MARGIN TRADING (prototype)
# -----------------------------------------------------
@app.post("/margin/trade")
def place_margin_trade(trade: TradeRequest):
    return {
        "message": "Margin trade placed successfully (prototype)",
        "trade": trade.dict()
    }

@app.get("/margin")
def get_margin():
    return {"message": "Margin trading endpoint (prototype)"}

# -----------------------------------------------------
# OTHER NAVBAR FEATURES (stubs)
# -----------------------------------------------------
@app.get("/earn")
def get_earn():
    return {"message": "Earn endpoint (prototype)"}

@app.get("/academy")
def get_academy():
    return {"message": "Academy endpoint (prototype)"}

@app.get("/markets")
def get_markets():
    return {"message": "Markets endpoint (prototype)"}

@app.get("/research")
def get_research():
    return {"message": "Research endpoint (prototype)"}

@app.get("/copy-trading")
def get_copy_trading():
    return {"message": "Copy trading endpoint (prototype)"}



