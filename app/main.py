from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Set, Dict, List
import uuid
import asyncio
import json
import time
import httpx 
import os # NEW: Import os for environment variable access
import random # NEW: Import random for price jittering

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

# ===============================
# 🔴 Real-time WebSocket + Prices
# ===============================

# --- Connection Manager ---
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
                await ws.send_text(text)
            except Exception:
                # Mark disconnected client for removal
                to_remove.add(ws)
        # Remove disconnected clients
        for ws in to_remove:
            self.active_connections.discard(ws)

manager = ConnectionManager()

# --- CoinGecko API Helper ---
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")  # Get optional API key

async def fetch_prices_from_coingecko():
    """Fetches real-time prices from CoinGecko, using Pro API key if available."""
    url = "https://api.coingecko.com/api/v3/simple/price"
    headers = {}
    
    # Use Pro API key if set in environment variables
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
    
    # Extract prices for BTC
    btc_usd = data.get("bitcoin", {}).get("usd")
    btc_inr = data.get("bitcoin", {}).get("inr")
    
    # Extract prices for ETH
    eth_usd = data.get("ethereum", {}).get("usd")
    eth_inr = data.get("ethereum", {}).get("inr")

    # Broadcast BTC data
    if btc_usd is not None and btc_inr is not None:
        await manager.broadcast({
            "type": "price_update",
            "symbol": "BTC/USDT",
            "usd": btc_usd,
            "inr": btc_inr,
            "timestamp": time.time()
        })
    
    # Broadcast ETH data
    if eth_usd is not None and eth_inr is not None:
        await manager.broadcast({
            "type": "price_update",
            "symbol": "ETH/USDT",
            "usd": eth_usd,
            "inr": eth_inr,
            "timestamp": time.time()
        })


# ---- CoinGecko Poller (Resilient Version) ----
async def coingecko_price_poller():
    """
    Polls CoinGecko API every 30s. Applies jitter every 5s.
    Uses cached prices and switches to a demo mode if too many errors occur.
    """
    # Initialize cache with safe starting values
    cache = {
        "bitcoin": {"usd": 50000.00, "inr": 4200000.00},
        "ethereum": {"usd": 3000.00, "inr": 250000.00}
    }
    
    TICK_INTERVAL = 5 # seconds
    POLL_INTERVAL_TICKS = 6 # 6 * 5s = 30s
    MAX_FAILURES = 3

    tick_count = 0
    failures = 0
    demo_mode = False

    while True:
        # 1. Attempt to fetch real data every 30 seconds (6 ticks of 5s)
        if tick_count % POLL_INTERVAL_TICKS == 0:
            try:
                # Fetches new real data
                new_data = await fetch_prices_from_coingecko()
                
                # If successful, update cache, reset failures, and exit demo mode
                cache = new_data
                failures = 0
                demo_mode = False
                print(f"✅ Updated prices from CoinGecko at {time.strftime('%H:%M:%S')}")
            
            except Exception as e:
                failures += 1
                error_message = str(e)
                
                # Check for rate limiting error (e.g., httpx.HTTPStatusError 429)
                if failures > MAX_FAILURES or "429" in error_message:
                    if not demo_mode:
                        print("🚨 CoinGecko rate limit exceeded (or other persistent error). Switching to DEMO mode.")
                        demo_mode = True
                
                print(f"⚠️ CoinGecko error (Failure {failures}): {e}")
                # Note: If demo_mode is True, the cache retains the last good price.

        # 2. Apply jitter to the current prices (from cache or last successful fetch)
        jittered_data = {}
        for sym, vals in cache.items():
            jittered_data[sym] = {
                cur: round(price * (1 + random.uniform(-0.001, 0.001)), 2)
                for cur, price in vals.items()
            }

        # 3. Broadcast the jittered data
        await broadcast_price_data(jittered_data)

        tick_count += 1
        await asyncio.sleep(TICK_INTERVAL) # The core loop runs every 5 seconds

# ---- WebSocket endpoint ----
@app.websocket("/ws/realtime")
async def websocket_endpoint(websocket: WebSocket):
    """Handles new WebSocket connections."""
    # Use manager to connect the client
    await manager.connect(websocket)
    try:
        # Keep the connection open to listen for client messages (like ping)
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text(json.dumps({"type": "pong", "ts": time.time()}))
            # Removed get_orders/init logic as global state is no longer managed here
    except WebSocketDisconnect:
        # Use manager to disconnect the client
        manager.disconnect(websocket)
    except Exception:
        # Ensure client is disconnected on any other error
        manager.disconnect(websocket)


# ---- Startup tasks ----
@app.on_event("startup")
async def start_background_tasks():
    """Starts the CoinGecko price poller task on application startup."""
    asyncio.create_task(coingecko_price_poller())
    print("✅ Realtime CoinGecko poller started")



