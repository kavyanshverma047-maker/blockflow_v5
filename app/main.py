from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Set, Dict, List
import uuid
import asyncio
import json
import time
import httpx 
import os 
import random 

# Import models for seeding and poller functions
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
    username: str # Added for demo user association
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
    # Order by price to show a better board
    return db.query(models.P2POrder).order_by(models.P2POrder.type.desc(), models.P2POrder.price.desc()).all()


# Helper function to run DB creation in a separate thread (synchronous)
def sync_create_p2p_order(db: Session, order: P2POrderRequest) -> models.P2POrder:
    # We allow the order to include 'username' for association, but the model only needs 'user_id'
    user = db.query(models.User).filter(models.User.username == order.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Use 'demo_user'.")

    # Fetch user's ID
    user_id = user.id

    # Cost check (simplified prototype logic)
    
    new_order = models.P2POrder(
        user_id=user_id,
        # Remove username mapping here since P2POrder model only expects user_id
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


@app.post("/p2p/orders")
async def create_p2p_order(order: P2POrderRequest, db: Session = Depends(get_db)):
    """
    Creates a new P2P order and broadcasts an 'order_update' event to all clients.
    """
    try:
        # 1. Run synchronous DB operation in a separate thread
        new_order = await asyncio.to_thread(sync_create_p2p_order, db, order)
    
        # 2. Broadcast the new order details to all clients
        # We need to fetch the associated username for the broadcast payload
        user = db.query(models.User).filter(models.User.id == new_order.user_id).first()
        username = user.username if user else "Unknown"

        # Use asyncio.create_task to non-blockingly broadcast the event
        asyncio.create_task(manager.broadcast({
            "type": "order_update",
            "order": {
                "id": new_order.id,
                "type": new_order.type,
                "price": new_order.price,
                "available": new_order.available,
                "limit_min": new_order.limit_min,
                "limit_max": new_order.limit_max,
                "merchant": new_order.merchant,
                "payment_method": new_order.payment_method,
                "user_id": new_order.user_id,
                "username": username, # Include username in broadcast for frontend
            }
        }))
        
        return new_order
    except HTTPException:
        # Re-raise FastAPIs exceptions
        raise
    except Exception as e:
        print(f"Error creating order: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@app.delete("/p2p/orders/{order_id}")
def delete_p2p_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.P2POrder).filter(models.P2POrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    db.delete(order)
    db.commit()
    
    # Broadcast a signal to remove the order from the board in real-time
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    asyncio.run_coroutine_threadsafe(manager.broadcast({
        "type": "order_delete",
        "order_id": order_id
    }), loop)

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

# ... (other stub endpoints remain unchanged)
# -----------------------------------------------------

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
                # Use send_text for efficiency, send_json is for dict inputs
                await ws.send_text(text) 
            except Exception:
                # Mark disconnected client for removal
                to_remove.add(ws)
        # Remove disconnected clients
        for ws in to_remove:
            self.active_connections.discard(ws)

manager = ConnectionManager()

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
    demo_user = db.query(models.User).filter_by(username="demo_user").first()
    if not demo_user:
        demo_user = models.User(
            username="demo_user",
            email="demo@blockflow.com",
            balance=100000.0 # Reduced for a more standard starting balance
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
             models.P2POrder(
                user_id=demo_user.id,
                merchant="P2P Buddy",
                type="Buy",
                price=49600, # Initial price, will be updated by poller
                available=0.2,
                limit_min=100,
                limit_max=1000,
                payment_method="IMPS"
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
                    # Tell frontend to refresh the board after prices change
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
                await websocket.send_text(json.dumps({"type": "pong", "ts": time.time()}))
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
