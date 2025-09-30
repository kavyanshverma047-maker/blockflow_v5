import os
import asyncio
import json
import time
import httpx 
import random 
from datetime import datetime, timedelta
from typing import Optional, Set, Dict, List, Any

# JWT and Auth specific imports
import jwt
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

# FastAPI and SQLAlchemy imports
from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import models (assuming they are correctly set up in app.models and app.database)
# The provided snippet uses 'from app.models import Base, User, P2POrder, Trade'
# We will rely on 'from app import models' and the initial setup.
from app import models
from app.database import Base, engine, SessionLocal # Assuming these still exist

# -----------------------------------------------------
# ---------- CONFIG & DB SETUP (Updated) ----------
# -----------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-demo-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Re-create engine/session based on the new snippet's standard structure
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Initialize database tables
models.Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -----------------------------------------------------
# Create FastAPI app
# -----------------------------------------------------
app = FastAPI(title="Blockflow Prototype Exchange")

# Enable CORS (for frontend integration)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ in prod, restrict to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------
# Schemas
# -----------------------------------------------------
class UserCreate(BaseModel):
    username: str
    email: str | None = None
    password: str | None = None # Added for JWT registration

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class P2POrderRequest(BaseModel):
    # Updated to remove 'username' dependency as user is identified by JWT
    type: str          # "Buy" or "Sell"
    merchant: str | None = None
    price: float
    available: float
    limit_min: float | None = None
    limit_max: float | None = None
    payment_method: str | None = None

class ExchangeTradeRequest(BaseModel):  # For Spot / Futures / Margin prototypes
    # Retained the old structure for prototype exchange endpoints
    username: str
    side: str        # "buy" or "sell"
    pair: str        # e.g. "BTC/USDT"
    amount: float
    price: float
    
class P2PTradeExecutionRequest(BaseModel):
    order_id: int
    taker_id: int  # user id of the taker (current_user.id should equal req.taker_id)
    amount: float


# -----------------------------------------------------
# ---------- AUTH HELPERS (from new snippet) ----------
# -----------------------------------------------------
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    """Dependency to retrieve the currently authenticated user."""
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    # Using models.User as per snippet's implied usage
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


# -----------------------------------------------------
# ---------- WEBSOCKET CONNECTION MANAGER (Existing) ----------
# -----------------------------------------------------
class ConnectionManager:
    """Manages active WebSocket connections and broadcasts messages."""
    def __init__(self):
        # Use a set for efficient connection tracking
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        """Accepts connection and adds it to the active set."""
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        """Removes a connection from the active set."""
        self.active_connections.discard(websocket)

    async def broadcast(self, payload: Dict):
        """Sends a JSON payload to all active WebSocket clients, handling disconnects."""
        text = json.dumps(payload, default=str)
        to_remove = set()
        # Iterate over a copy to allow modification during iteration
        for ws in list(self.active_connections):
            try:
                # Use send_text for efficiency
                await ws.send_text(text) 
            except Exception:
                # Mark disconnected client for removal
                to_remove.add(ws)
        # Remove disconnected clients
        for ws in to_remove:
            self.active_connections.discard(ws)

manager = ConnectionManager()


# -----------------------------------------------------
# ---------- ENDPOINTS ----------
# -----------------------------------------------------

# Root healthcheck
@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "Blockflow API",
        "message": "Backend is running successfully 🚀"
    }

# --- Auth Endpoints ---
@app.post("/register", response_model=Dict)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    """Registers a new user and returns a JWT token."""
    existing = db.query(models.User).filter(models.User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # NOTE: Password is NOT saved or checked for this demo, only username is used for token generation
    user = models.User(username=payload.username, email=payload.email, balance=100000.0)
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"user_id": user.id})
    return {"id": user.id, "username": user.username, "email": user.email, "access_token": token}

@app.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Authenticates a user and returns a JWT token."""
    # For demo we accept any password if username exists.
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    token = create_access_token({"user_id": user.id})
    return {"access_token": token, "token_type": "bearer"}

# --- Users Endpoint ---
@app.get("/users")
def list_users(db: Session = Depends(get_db)):
    """Lists all users (Public endpoint for demo purposes)."""
    users = db.query(models.User).all()
    # Mask password field, include balance
    return [{"id": u.id, "username": u.username, "email": u.email, "balance": u.balance} for u in users]


# -----------------------------------------------------
# P2P ORDERS (Updated with Auth & WebSocket Broadcasts)
# -----------------------------------------------------
def _get_p2p_orders_payload(db: Session) -> List[Dict[str, Any]]:
    """Helper to fetch and format the current P2P order list."""
    orders = db.query(models.P2POrder).all()
    # Fetch usernames for display
    user_map = {u.id: u.username for u in db.query(models.User).all()}
    
    return [
        {"id": o.id, "user_id": o.user_id, "merchant": o.merchant, "type": o.type, 
         "price": o.price, "available": o.available, "limit_min": o.limit_min, 
         "limit_max": o.limit_max, "payment_method": o.payment_method, 
         "username": user_map.get(o.user_id, "Unknown")}
        for o in orders
    ]


@app.get("/p2p/orders")
def list_p2p_orders(db: Session = Depends(get_db)):
    """Lists all P2P orders."""
    # Order by price to show a better board
    return db.query(models.P2POrder).order_by(models.P2POrder.type.desc(), models.P2POrder.price.desc()).all()


@app.post("/p2p/orders")
def create_p2p_order(req: P2POrderRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Creates a new P2P order (protected by JWT)."""
    # Basic validation
    if req.price <= 0 or req.available <= 0:
        raise HTTPException(status_code=422, detail="Price and available amount must be > 0")
        
    order = models.P2POrder(
        user_id=current_user.id,
        type=req.type,
        merchant=req.merchant or current_user.username,
        price=req.price,
        available=req.available,
        limit_min=req.limit_min,
        limit_max=req.limit_max,
        payment_method=req.payment_method
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    # 1. Broadcast single order update
    asyncio.create_task(manager.broadcast({"type": "order_update", "action": "created", "order": {
        "id": order.id,
        "user_id": order.user_id,
        "merchant": order.merchant,
        "type": order.type,
        "price": order.price,
        "available": order.available,
        "limit_min": order.limit_min,
        "limit_max": order.limit_max,
        "payment_method": order.payment_method,
        "username": current_user.username # Include username
    }}))

    # 2. Broadcast updated order list snapshot
    asyncio.create_task(manager.broadcast({"type": "order_list", "orders": _get_p2p_orders_payload(db)}))

    return {"id": order.id, "user_id": order.user_id, "price": order.price, "available": order.available}


@app.delete("/p2p/orders/{order_id}")
def delete_p2p_order(order_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Deletes a P2P order (protected by JWT, only owner can delete)."""
    order = db.query(models.P2POrder).filter(models.P2POrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this order")
        
    db.delete(order)
    db.commit()
    
    # Broadcast signal to remove the order
    asyncio.create_task(manager.broadcast({"type": "order_update", "action": "deleted", "order_id": order_id}))
    # Broadcast current order list snapshot
    asyncio.create_task(manager.broadcast({"type": "order_list", "orders": _get_p2p_orders_payload(db)}))

    return {"message": "Order deleted successfully"}


@app.post("/p2p/trade")
def execute_trade(req: P2PTradeExecutionRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Executes a P2P trade, updating balances and orders.
    Requires JWT authentication.
    """
    if current_user.id != req.taker_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Taker ID must match authenticated user ID")

    order = db.query(models.P2POrder).filter(models.P2POrder.id == req.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    if order.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot trade against your own order")

    if req.amount <= 0 or req.amount > order.available:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid trade amount")

    # Determine buyer/seller
    if order.type.lower() == "sell": # Order is "Sell", so owner is selling BTC; Taker is BUYER (paying money)
        seller = db.query(models.User).filter(models.User.id == order.user_id).first()
        buyer = db.query(models.User).filter(models.User.id == req.taker_id).first()
    else: # order.type == "Buy" => order owner is BUYER (receiving BTC); Taker is SELLER (receiving money)
        buyer = db.query(models.User).filter(models.User.id == order.user_id).first()
        seller = db.query(models.User).filter(models.User.id == req.taker_id).first()

    if not buyer or not seller:
        raise HTTPException(status_code=404, detail="Buyer or seller user not found")

    total_value = order.price * req.amount

    # Simple balance checks (buyer must have fiat balance >= total_value)
    if buyer.balance < total_value:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Buyer's balance insufficient")

    # Update balances (prototypical fiat transfer)
    buyer.balance -= total_value
    seller.balance += total_value

    # Reduce or delete order
    order.available -= req.amount
    is_filled = order.available <= 1e-9 # Check if completely filled
    if is_filled:
        db.delete(order)
        
    # Save trade record (using models.Trade)
    trade = models.Trade(buyer_id=buyer.id, seller_id=seller.id, price=order.price, amount=req.amount)
    db.add(trade)
    db.commit()
    
    # Refresh users/order state
    db.refresh(buyer)
    db.refresh(seller)
    
    # Broadcast: trade_executed, balances, orders
    asyncio.create_task(manager.broadcast({
        "type": "trade_executed",
        "trade": {"id": trade.id, "buyer_id": trade.buyer_id, "seller_id": trade.seller_id, 
                  "price": trade.price, "amount": trade.amount, "order_id": order.id if not is_filled else None}
    }))

    asyncio.create_task(manager.broadcast({
        "type": "balance_update",
        "users": [
            {"id": buyer.id, "username": buyer.username, "balance": buyer.balance},
            {"id": seller.id, "username": seller.username, "balance": seller.balance}
        ]
    }))

    # broadcast current order list snapshot
    asyncio.create_task(manager.broadcast({
        "type": "order_list",
        "orders": _get_p2p_orders_payload(db)
    }))

    return {"trade_id": trade.id, "buyer_balance": buyer.balance, "seller_balance": seller.balance}


# -----------------------------------------------------
# SPOT TRADING ENDPOINTS (Prototypes - using ExchangeTradeRequest)
# -----------------------------------------------------
@app.post("/spot/trade")
def place_spot_trade(trade: ExchangeTradeRequest, db: Session = Depends(get_db)):
    # Assuming models.SpotTrade exists in app/models.py
    new_trade = models.SpotTrade(**trade.dict())
    db.add(new_trade)
    db.commit()
    db.refresh(new_trade)
    return new_trade

@app.get("/spot/orders")
def list_spot_orders(db: Session = Depends(get_db)):
    # Assuming models.SpotTrade exists in app/models.py
    return db.query(models.SpotTrade).all()

# -----------------------------------------------------
# MARGIN TRADING ENDPOINTS (Prototypes - using ExchangeTradeRequest)
# -----------------------------------------------------
@app.post("/margin/trade")
def place_margin_trade(trade: ExchangeTradeRequest, db: Session = Depends(get_db)):
    # Assuming models.MarginTrade exists in app/models.py
    new_trade = models.MarginTrade(**trade.dict())
    db.add(new_trade)
    db.commit()
    db.refresh(new_trade)
    return new_trade

@app.get("/margin/orders")
def list_margin_orders(db: Session = Depends(get_db)):
    # Assuming models.MarginTrade exists in app/models.py
    return db.query(models.MarginTrade).all()

# -----------------------------------------------------
# FUTURES (USDM) TRADING ENDPOINTS (Prototypes - using ExchangeTradeRequest)
# -----------------------------------------------------
@app.post("/futures/usdm/trade")
def place_usdm_futures_trade(trade: ExchangeTradeRequest, db: Session = Depends(get_db)):
    # Assuming models.FuturesUsdmTrade exists in app/models.py
    new_trade = models.FuturesUsdmTrade(**trade.dict())
    db.add(new_trade)
    db.commit()
    db.refresh(new_trade)
    return new_trade

@app.get("/futures/usdm/orders")
def list_usdm_futures_orders(db: Session = Depends(get_db)):
    # Assuming models.FuturesUsdmTrade exists in app/models.py
    return db.query(models.FuturesUsdmTrade).all()

# -----------------------------------------------------
# FUTURES (COINM) TRADING ENDPOINTS (Prototypes - using ExchangeTradeRequest)
# -----------------------------------------------------
@app.post("/futures/coinm/trade")
def place_coinm_futures_trade(trade: ExchangeTradeRequest, db: Session = Depends(get_db)):
    # Assuming models.FuturesCoinmTrade exists in app/models.py
    new_trade = models.FuturesCoinmTrade(**trade.dict())
    db.add(new_trade)
    db.commit()
    db.refresh(new_trade)
    return new_trade

@app.get("/futures/coinm/orders")
def list_coinm_futures_orders(db: Session = Depends(get_db)):
    # Assuming models.FuturesCoinmTrade exists in app/models.py
    return db.query(models.FuturesCoinmTrade).all()

# -----------------------------------------------------
# OPTIONS TRADING ENDPOINTS (Prototypes - using ExchangeTradeRequest)
# -----------------------------------------------------
@app.post("/options/trade")
def place_options_trade(trade: ExchangeTradeRequest, db: Session = Depends(get_db)):
    # Assuming models.OptionsTrade exists in app/models.py
    new_trade = models.OptionsTrade(**trade.dict())
    db.add(new_trade)
    db.commit()
    db.refresh(new_trade)
    return new_trade

@app.get("/options/orders")
def list_options_orders(db: Session = Depends(get_db)):
    # Assuming models.OptionsTrade exists in app/models.py
    return db.query(models.OptionsTrade).all()

# -----------------------------------------------------
# ===============================
# 🔴 Real-time WebSocket + Prices (Existing)
# ===============================

# --- CoinGecko API Helper ---
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY") 

async def fetch_prices_from_coingecko():
    """Fetches real-time prices from CoinGecko, using Pro API key if available."""
    url = "https://api.coingecko.com/api/v3/simple/price"
    headers = {}
    
    if COINGECKO_API_KEY:
        headers["x-cg-pro-api-key"] = COINGECKO_API_KEY 

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            url,
            params={"ids": "bitcoin,ethereum", "vs_currencies": "usd,inr"},
            headers=headers
        )
        resp.raise_for_status()
        return resp.json()

async def broadcast_price_data(data: Dict):
    """Parses CoinGecko response and broadcasts individual updates."""
    
    # Map CoinGecko IDs to our symbols and extract data
    symbols_map = {
        "bitcoin": "BTC/USDT",
        "ethereum": "ETH/USDT"
    }
    
    for cg_id, symbol in symbols_map.items():
        usd_price = data.get(cg_id, {}).get("usd")
        inr_price = data.get(cg_id, {}).get("inr")

        if usd_price is not None and inr_price is not None:
            # Broadcast data
            await manager.broadcast({
                "type": "price_update",
                "symbol": symbol,
                "usd": usd_price,
                "inr": inr_price,
                # Convert time to milliseconds for easy JS processing
                "timestamp": int(time.time() * 1000) 
            })


# ---- Synchronous DB Helpers (for use with asyncio.to_thread) ----

def sync_update_p2p_orders(db: Session, btc_inr_price: float):
    """Updates P2P Buy and Sell order prices based on the live BTC price."""
    # Fetch all orders (for this demo)
    orders = db.query(models.P2POrder).all()
    updated_count = 0
    
    # Arbitrary buffers to simulate a spread around the market price
    SELL_MARKUP = 1.015 # 1.5% above market for Sell orders
    BUY_DISCOUNT = 0.985 # 1.5% below market for Buy orders

    for order in orders:
        new_price = None
        
        # NOTE: This assumes all P2P orders are for BTC. 
        if order.type == "Sell":
            # Set the Sell price (what a user pays) slightly above market
            new_price = btc_inr_price * SELL_MARKUP
        elif order.type == "Buy":
            # Set the Buy price (what a user receives) slightly below market
            new_price = btc_inr_price * BUY_DISCOUNT
        
        if new_price is not None:
            order.price = round(new_price, 0)
            db.add(order)
            updated_count += 1
            
    db.commit()
    if updated_count > 0:
        print(f"🔄 Auto-synced {updated_count} P2P orders to new BTC price: ₹{int(btc_inr_price)}")


def sync_seed_demo_data(db: Session):
    """Seed demo user and a few demo orders for P2P page."""
    # Create demo user if not exists
    demo_user = db.query(models.User).filter_by(username="demo_user").first()
    if not demo_user:
        demo_user = models.User(
            username="demo_user",
            email="demo@blockflow.com",
            balance=100000.0 # Standard starting balance
        )
        db.add(demo_user)
        db.commit()
        db.refresh(demo_user)

    # Only seed orders if none exist
    existing_orders = db.query(models.P2POrder).count()
    if existing_orders == 0:
        demo_orders = [
            models.P2POrder(
                user_id=demo_user.id,
                merchant="Blockflow Merchant",
                type="Buy",
                price=49500, # Initial price, will be updated by poller
                available=0.05,
                limit_min=500,
                limit_max=2000,
                payment_method="UPI"
            ),
            models.P2POrder(
                user_id=demo_user.id,
                merchant="Blockflow Merchant",
                type="Sell",
                price=50500, # Initial price, will be updated by poller
                available=0.08,
                limit_min=1000,
                limit_max=5000,
                payment_method="Bank Transfer"
            ),
        ]
        db.add_all(demo_orders)
        db.commit()
        print("✅ Initial P2P demo orders created.")
    print("✅ Demo data seeding complete.")


# ---- CoinGecko Poller (Resilient Version) ----
async def coingecko_price_poller():
    """Polls CoinGecko API for price data and updates P2P orders."""
    # Initialize cache with safe starting values
    cache = {
        "bitcoin": {"usd": 50000.00, "inr": 4200000.00},
        "ethereum": {"usd": 3000.00, "inr": 250000.00}
    }
    
    TICK_INTERVAL = 5 # seconds (Jitter/Broadcast frequency)
    POLL_INTERVAL_TICKS = 6 # 6 * 5s = 30s (API poll frequency)
    MAX_FAILURES = 3

    tick_count = 0
    failures = 0
    demo_mode = False

    while True:
        # 1. Attempt to fetch real data every 30 seconds
        if tick_count % POLL_INTERVAL_TICKS == 0:
            try:
                new_data = await fetch_prices_from_coingecko()
                
                cache = new_data
                failures = 0
                demo_mode = False
                print(f"✅ Updated prices from CoinGecko at {time.strftime('%H:%M:%S')}")
            
            except Exception as e:
                failures += 1
                error_message = str(e)
                
                if failures > MAX_FAILURES or "429" in error_message:
                    if not demo_mode:
                        print("🚨 CoinGecko rate limit exceeded (or other persistent error). Switching to DEMO mode.")
                        demo_mode = True
                
                print(f"⚠️ CoinGecko error (Failure {failures}): {e}")

        # 2. Apply jitter to the current prices
        jittered_data = {}
        for sym, vals in cache.items():
            jittered_data[sym] = {
                cur: round(price * (1 + random.uniform(-0.001, 0.001)), 2)
                for cur, price in vals.items()
            }

        # 3. Broadcast the jittered data
        await broadcast_price_data(jittered_data)
        
        # 4. Auto-sync P2P Sell/Buy Orders to the Jittered BTC/INR Price (Every 30s tick)
        if tick_count % POLL_INTERVAL_TICKS == 0:
            btc_inr_price = jittered_data.get("bitcoin", {}).get("inr")
            if btc_inr_price is not None:
                db_sync = SessionLocal()
                try:
                    # Run the synchronous database update in a separate thread
                    await asyncio.to_thread(sync_update_p2p_orders, db_sync, btc_inr_price)
                    # Broadcast to trigger frontend P2P order list refresh
                    await manager.broadcast({"type": "orders_refresh"}) 
                finally:
                    db_sync.close()

        tick_count += 1
        await asyncio.sleep(TICK_INTERVAL) 

# ---- WebSocket endpoint ----
@app.websocket("/ws") 
async def websocket_endpoint(websocket: WebSocket):
    """Handles new WebSocket connections."""
    await manager.connect(websocket)
    try:
        while True:
            # Optionally listen for client messages (e.g., subscription requests)
            msg = await websocket.receive_text()
            if msg == "ping":
                # Respond with a standard pong message
                await websocket.send_text(json.dumps({"type": "pong", "ts": int(time.time() * 1000)}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


# ---- Startup tasks ----
@app.on_event("startup")
async def start_background_tasks():
    """Seeds demo data and starts the CoinGecko price poller task on application startup."""
    print("🚀 App starting up...")
    
    # 1. Seed demo data first (run sync function in a thread)
    db_sync = SessionLocal()
    try:
        await asyncio.to_thread(sync_seed_demo_data, db_sync)
    finally:
        db_sync.close()
    
    # 2. Start the price poller (async task)
    asyncio.create_task(coingecko_price_poller())
    print("✅ Realtime CoinGecko poller started")

    
    # 2. Start the price poller (async task)
    asyncio.create_task(coingecko_price_poller())
    print("✅ Realtime CoinGecko poller started")
