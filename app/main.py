from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Set, Dict
import uuid
import asyncio
import json
import time
import websockets

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
# Track connected websocket clients
realtime_clients: Set[WebSocket] = set()

# Global realtime state
realtime_state: Dict = {
    "btc_inr": None,
    "btc_usd": None,
    "usd_inr": None,
    "last_update": 0,
    "orders": []
}

# ---- Broadcast helper ----
async def broadcast_state():
    """Sends the current state to all connected WebSocket clients."""
    payload = {"type": "price_update", "data": realtime_state}
    text = json.dumps(payload, default=str)
    to_remove = set()
    # Use list(realtime_clients) to iterate over a copy, avoiding errors if a client disconnects mid-loop
    for ws in list(realtime_clients):
        try:
            await ws.send_text(text)
        except Exception:
            # Mark disconnected client for removal
            to_remove.add(ws)
    # Remove disconnected clients
    for ws in to_remove:
        realtime_clients.discard(ws)

# ---- Binance BTC/USDT price listener ----
async def binance_trade_listener():
    """Connects to Binance WS for real-time BTC/USDT trades and updates state."""
    BINANCE_WS = "wss://stream.binance.com:9443/ws/btcusdt@trade"
    while True:
        try:
            # Use websockets library for client connection
            async with websockets.connect(BINANCE_WS, ping_interval=20, ping_timeout=10) as ws:
                async for message in ws:
                    msg = json.loads(message)
                    price_str = msg.get("p")
                    if price_str:
                        btc_usd = float(price_str)
                        realtime_state["btc_usd"] = btc_usd
                        realtime_state["last_update"] = time.time()
                        # Calculate BTC/INR if the exchange rate is known
                        if realtime_state.get("usd_inr"):
                            realtime_state["btc_inr"] = btc_usd * realtime_state["usd_inr"]
                        await broadcast_state()
        except Exception as e:
            # Print error and wait before attempting to reconnect
            print("Binance WS error, reconnecting:", e)
            await asyncio.sleep(3)

# ---- CoinGecko USD→INR poller ----
async def coin_gecko_usd_inr_poller():
    """
    Polls CoinGecko API for BTC/INR, BTC/USD, and calculates USD/INR rate.
    NOTE: This task currently uses 'aiohttp' functionality (ClientSession, session.get),
    but the 'aiohttp' import was removed per user request. This task will now fail at runtime
    unless an alternative HTTP client is implemented or 'aiohttp' is re-imported.
    """
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=inr,usd"
    # Placeholder/commented out code below due to missing `aiohttp` import
    # async with aiohttp.ClientSession() as session:
    #     while True:
    #         try:
    #             async with session.get(url) as resp:
    #                 if resp.status == 200:
    #                     d = await resp.json()
    #                     btc_inr = d["bitcoin"]["inr"]
    #                     btc_usd = d["bitcoin"]["usd"]
    #                     # Calculate the implied USD/INR exchange rate
    #                     usd_inr = btc_inr / btc_usd
    #                     realtime_state["usd_inr"] = usd_inr

    #                     # If we have the real-time BTC/USD from Binance, use it to calculate BTC/INR
    #                     if realtime_state.get("btc_usd"):
    #                         realtime_state["btc_inr"] = realtime_state["btc_usd"] * usd_inr
                        
    #                     realtime_state["last_update"] = time.time()
    #                     await broadcast_state()
    #         except Exception as e:
    #             print("CoinGecko error:", e)
    #         # Poll every 5 seconds
    #         await asyncio.sleep(5)
    
    # Simple placeholder loop to prevent the task from immediately crashing if not fully removed
    while True:
        await asyncio.sleep(5)
        print("CoinGecko poller is currently inactive due to missing HTTP library.")

# ---- WebSocket endpoint ----
@app.websocket("/ws/realtime")
async def websocket_endpoint(websocket: WebSocket):
    """Handles new WebSocket connections for real-time updates."""
    await websocket.accept()
    realtime_clients.add(websocket)
    try:
        # send initial snapshot on connection
        await websocket.send_text(json.dumps({"type": "init", "data": realtime_state}, default=str))
        while True:
            # Listen for incoming messages (e.g., ping)
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text(json.dumps({"type": "pong", "ts": time.time()}))
            elif msg == "get_orders":
                # Send current orders list (if implemented)
                await websocket.send_text(json.dumps({"type": "orders_update", "data": realtime_state.get("orders", [])}, default=str))
    except WebSocketDisconnect:
        # Client gracefully disconnected
        realtime_clients.discard(websocket)
    except Exception:
        # Client disconnected due to an error
        realtime_clients.discard(websocket)

# ---- Startup tasks ----
@app.on_event("startup")
async def startup_event():
    """Starts the background listeners for real-time price updates."""
    loop = asyncio.get_event_loop()
    # Create background tasks for fetching/listening to data
    loop.create_task(binance_trade_listener())
    loop.create_task(coin_gecko_usd_inr_poller())
    print("✅ Realtime tasks started")



