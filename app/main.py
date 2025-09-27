from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
import uuid

from app import models
from app.database import Base, engine, SessionLocal
from fastapi.middleware.cors import CORSMiddleware

# -----------------------------------------------------
# Create FastAPI app
# -----------------------------------------------------
app = FastAPI(title="Blockflow Prototype Exchange")

# -----------------------------------------------------
# DB Initialization
# -----------------------------------------------------
models.Base.metadata.create_all(bind=engine)

# -----------------------------------------------------
# Enable CORS (for frontend calls)
# -----------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict to frontend URL in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------
# DB Dependency
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
    email: str | None = None

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

# -----------------------------------------------------
# Root Healthcheck
# -----------------------------------------------------
@app.get("/")
def root():
    return {"status": "ok", "service": "Blockflow API", "message": "Backend is running successfully 🚀"}

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
# P2P (real logic)
# -----------------------------------------------------
@app.get("/p2p/orders")
def list_p2p_orders(db: Session = Depends(get_db)):
    return db.query(models.P2POrder).all()

@app.post("/p2p/orders")
def create_p2p_order(order: P2POrderRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == order.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    cost = order.available * order.price
    if order.type.lower() == "buy":
        if getattr(user, "balance", 0) < cost:  # fallback if balance not implemented
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





# =====================================================
# SPOT & MARGIN TRADING
# =====================================================

@app.post("/spot/trade")
def spot_trade(trade: TradeRequest, db: Session = Depends(get_db)):
    return {"message": "Spot trade executed (stub)", "trade": trade.dict()}

@app.get("/spot/orders")
def spot_orders(username: str):
    return {"username": username, "orders": []}

@app.post("/margin/trade")
def margin_trade(trade: TradeRequest):
    return {"message": "Margin trade executed (stub)", "trade": trade.dict()}

@app.get("/margin/orders")
def margin_orders(username: str):
    return {"username": username, "orders": []}


# =====================================================
# P2P TRADING (real logic)
# =====================================================

@app.get("/p2p/orders")
def list_p2p_orders(db: Session = Depends(get_db)):
    return db.query(models.P2POrder).all()

@app.post("/p2p/orders")
def create_p2p_order(order: P2POrderRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == order.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

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


# =====================================================
# FUTURES + OPTIONS
# =====================================================

@app.post("/futures/usdm/trade")
def futures_usdm_trade(trade: TradeRequest):
    return {"message": "USDM Futures trade executed (stub)", "trade": trade.dict()}

@app.get("/futures/usdm/orders")
def futures_usdm_orders(username: str):
    return {"username": username, "orders": []}

@app.post("/futures/coinm/trade")
def futures_coinm_trade(trade: TradeRequest):
    return {"message": "COIN-M Futures trade executed (stub)", "trade": trade.dict()}

@app.get("/futures/coinm/orders")
def futures_coinm_orders(username: str):
    return {"username": username, "orders": []}

@app.post("/options/trade")
def options_trade(trade: TradeRequest):
    return {"message": "Options trade executed (stub)", "trade": trade.dict()}

@app.get("/options/orders")
def options_orders(username: str):
    return {"username": username, "orders": []}


# =====================================================
# EARN
# =====================================================

@app.post("/earn/stake")
def earn_stake(username: str, amount: float):
    return {"message": f"{amount} staked for {username} (stub)"}

@app.get("/earn/stakes")
def earn_stakes(username: str):
    return {"username": username, "stakes": []}

@app.post("/earn/save")
def earn_save(username: str, amount: float):
    return {"message": f"{amount} saved for {username} (stub)"}

@app.get("/earn/savings")
def earn_savings(username: str):
    return {"username": username, "savings": []}

@app.post("/earn/launchpool/join")
def earn_launchpool(username: str, project: str):
    return {"message": f"{username} joined Launchpool for {project} (stub)"}

@app.get("/earn/launchpool")
def earn_launchpool_info():
    return {"projects": [{"name": "ProjectX", "apr": "15%"}]}


# =====================================================
# BUY CRYPTO & MARKETS
# =====================================================

@app.post("/buycrypto")
def buy_crypto(username: str, amount: float, currency: str):
    return {"message": f"{username} bought {amount} {currency} (stub)"}

@app.get("/markets")
def get_markets():
    return {"markets": [
        {"pair": "BTC/USDT", "price": 50000},
        {"pair": "ETH/USDT", "price": 3500},
    ]}


# =====================================================
# ACADEMY + RESEARCH
# =====================================================

@app.get("/academy/articles")
def academy_articles():
    return {"articles": [
        {"title": "What is Blockchain?", "id": 1},
        {"title": "Intro to Crypto Trading", "id": 2},
    ]}

@app.get("/research/reports")
def research_reports():
    return {"reports": [
        {"title": "Q1 Market Outlook", "id": "R1"},
        {"title": "BTC Adoption Curve", "id": "R2"},
    ]}


# =====================================================
# STATS
# =====================================================

@app.get("/stats/transactions")
def stats_transactions():
    return {"total_volume": "10B USD", "transactions": 123456}

@app.get("/stats/demo")
def stats_demo():
    return {"demo_trades_processed": 98765}

@app.get("/stats/markets")
def stats_markets():
    return {"market_listings": 120}

@app.get("/stats/pairs")
def stats_pairs():
    return {"trading_pairs": 340}


