# main.py
"""
Blockflow Full Backend — Expanded Variant (~701 lines)
- Fully standalone FastAPI backend with:
  - JWT auth (register/login)
  - Users listing
  - P2P orderbook (list/create/delete)
  - P2P trade execution (balance updates, trade records)
  - Spot endpoints (orderbook, candles, trade history, place trade)
  - Prototypes: margin, futures (usdm/coinm), options (DB-backed)
  - WebSockets:
      - /ws : app-level broadcast socket (p2p/order updates, price updates)
      - /ws/market : market simulator (ticker, trades, orderbook snapshots)
  - CoinGecko poller (resilient) with jitter + P2P auto-sync
  - Rich mock-data generators and verbose logging for demo & testing
- Designed for development/demo only. Do NOT use in production as-is.
"""
# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------
import os
import time
import json
import random
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Third-party imports
# ---------------------------------------------------------------------------
import httpx
import jwt
from pydantic import BaseModel
from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    Depends,
    HTTPException,
    status,
    Query,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# ---------------------------------------------------------------------------
# Logging setup — verbose for demo
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.DEBUG),
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
)
logger = logging.getLogger("blockflow-main")
logger.info("Starting Blockflow expanded backend...")

# ---------------------------------------------------------------------------
# Try to import user's models & database (support both app package and root files)
# ---------------------------------------------------------------------------
models = None
SessionLocal = None
engine = None
Base = None

try:
    # Preferred: project structured as package `app`
    from app import models as app_models  # type: ignore
    from app.database import SessionLocal as AppSessionLocal, engine as AppEngine, Base as AppBase  # type: ignore
    models = app_models
    SessionLocal = AppSessionLocal
    engine = AppEngine
    Base = AppBase
    logger.info("Imported models from app package (app.models, app.database).")
except Exception as e_app:
    logger.debug("app package import failed: %s", e_app)
    try:
        # Fallback: local files `models.py`, `database.py`
        import models as local_models  # type: ignore
        from database import SessionLocal as LocalSessionLocal, engine as LocalEngine, Base as LocalBase  # type: ignore
        models = local_models
        SessionLocal = LocalSessionLocal
        engine = LocalEngine
        Base = LocalBase
        logger.info("Imported models from local files (models.py, database.py).")
    except Exception as e_local:
        logger.error("Could not import models/database from app or local: %s | %s", e_app, e_local)
        logger.warning("Many endpoints will be disabled until models/database are available.")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./blockflow.db")
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-demo-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")
# Polling frequency and jitter settings for demo
POLL_TICK_INTERVAL = int(os.getenv("POLL_TICK_INTERVAL", "5"))  # seconds
POLL_INTERVAL_TICKS = int(os.getenv("POLL_INTERVAL_TICKS", "6"))  # number of ticks between full polls (5*6=30s)
MAX_CG_FAILURES = int(os.getenv("MAX_CG_FAILURES", "3"))

# ---------------------------------------------------------------------------
# Ensure SessionLocal exists (create fallback if imports failed)
# ---------------------------------------------------------------------------
if SessionLocal is None:
    logger.warning("SessionLocal not found from imports; creating local engine/session from DATABASE_URL.")
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ---------------------------------------------------------------------------
# Create DB tables if models present and Base exists
# ---------------------------------------------------------------------------
if models is not None and hasattr(models, "Base"):
    try:
        models.Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified.")
    except Exception as e:
        logger.exception("Error creating DB tables: %s", e)

# ---------------------------------------------------------------------------
# FastAPI app creation
# ---------------------------------------------------------------------------
app = FastAPI(title="Blockflow Expanded Backend", version="1.0.0-expanded")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo: allow all origins. Lock this down in production.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Utility: DB session dependency
# ---------------------------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------------------------------------------------------------------
# JWT helpers (very simple demo style)
# ---------------------------------------------------------------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    logger.debug("Created JWT token for payload keys: %s", list(data.keys()))
    return encoded

def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError as e:
        logger.debug("Failed to decode token: %s", e)
        return None

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_token(token)
    if not payload:
        logger.debug("Token decode returned no payload.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
    user_id = payload.get("user_id")
    if not user_id:
        logger.debug("Token missing user_id.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if models is None:
        logger.error("User model not available - models import failed.")
        raise HTTPException(status_code=500, detail="User model not available")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        logger.debug("User id %s not found in DB.", user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

# ---------------------------------------------------------------------------
# WebSocket Connection Manager — robust and simple
# ---------------------------------------------------------------------------
class ConnectionManager:
    """
    Tracks active websocket clients and provides broadcast helpers.
    Uses a set for efficient membership checks.
    """
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.debug("WebSocket connected. Total clients: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.debug("WebSocket disconnected. Remaining clients: %d", len(self.active_connections))

    async def broadcast(self, payload: Dict[str, Any]):
        """
        Sends JSON (text) to all active clients.
        Removes sockets which raise exceptions (stale clients).
        """
        text = json.dumps(payload, default=str)
        to_remove: Set[WebSocket] = set()
        for ws in list(self.active_connections):
            try:
                await ws.send_text(text)
            except Exception as e:
                logger.debug("Error sending to ws client: %s", e)
                to_remove.add(ws)
        for ws in to_remove:
            self.active_connections.discard(ws)
        logger.debug("Broadcasted payload to %d clients: %s", len(self.active_connections), payload.get("type"))

    async def broadcast_json(self, payload: Any):
        # Convenience wrapper — allow both dicts and other types
        if isinstance(payload, dict):
            await self.broadcast(payload)
        else:
            await self.broadcast({"payload": payload})

manager = ConnectionManager()

# ---------------------------------------------------------------------------
# Pydantic Schemas used by endpoints
# ---------------------------------------------------------------------------
class UserCreate(BaseModel):
    username: str
    email: Optional[str] = None
    password: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class P2POrderRequest(BaseModel):
    type: str  # "Buy" or "Sell"
    merchant: Optional[str] = None
    price: float
    available: float
    limit_min: Optional[float] = None
    limit_max: Optional[float] = None
    payment_method: Optional[str] = None

class ExchangeTradeRequest(BaseModel):
    username: str
    side: str  # "buy" | "sell"
    pair: str
    amount: float
    price: float

class P2PTradeExecutionRequest(BaseModel):
    order_id: int
    taker_id: int
    amount: float

# ---------------------------------------------------------------------------
# Market helpers & mock data generators (expanded + verbose)
# ---------------------------------------------------------------------------
def now_ms() -> int:
    return int(time.time() * 1000)

def jitter(val: float, pct: float = 0.001) -> float:
    """
    Small multiplicative jitter applied to prices to make generated market data feel alive.
    Default: 0.1% jitter.
    """
    return val * (1 + random.uniform(-pct, pct))

# Base prices used by the market simulator
BASE_PRICE = 65000.0
SYMBOLS: Dict[str, float] = {"BTCUSDT": BASE_PRICE, "ETHUSDT": 3200.0, "XRPUSDT": 0.45, "SOLUSDT": 110.0}

def gen_orderbook(mid: float, depth: int = 20, spread_min: float = 0.1, spread_max: float = 3.0) -> Tuple[List[List[float]], List[List[float]]]:
    """
    Generates a synthetic orderbook with `depth` levels.
    Returns (bids, asks). Each entry is [price, qty].
    Prices step away from mid using a random multiplier in range [spread_min, spread_max].
    """
    bids = []
    asks = []
    for i in range(depth):
        step = (i + 1) * random.uniform(spread_min, spread_max)
        bid_price = round(mid - step, 8 if mid < 1 else 2)
        ask_price = round(mid + step, 8 if mid < 1 else 2)
        bid_qty = round(random.uniform(0.0001, 5.0), 6)
        ask_qty = round(random.uniform(0.0001, 5.0), 6)
        bids.append([bid_price, bid_qty])
        asks.append([ask_price, ask_qty])
    return bids, asks

def gen_trades_history(symbol: str, base: float, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Generates a list of recent trades for a symbol (newest first).
    Each trade has price, qty, side, ts.
    """
    trades = []
    now = now_ms()
    for i in range(limit):
        price = round(base + random.uniform(-0.02 * base, 0.02 * base), 8 if base < 1 else 2)
        qty = round(random.uniform(0.0001, 10.0), 6)
        side = random.choice(["buy", "sell"])
        ts = now - i * random.randint(100, 2000)  # spaced randomly between 100ms and 2s
        trades.append({"price": price, "qty": qty, "side": side, "ts": ts})
    return trades

def gen_candles(base: float, interval_seconds: int = 60, limit: int = 200) -> List[Dict[str, Any]]:
    """
    Generates OHLCV candles. Each candle spaced by interval_seconds.
    Returns older -> newer (time ascending) with ts in ms.
    """
    candles: List[Dict[str, Any]] = []
    t_now = int(time.time())
    for i in range(limit):
        # Create pseudo-random walk
        o = base + random.uniform(-0.03 * base, 0.03 * base)
        c = o + random.uniform(-0.02 * base, 0.02 * base)
        h = max(o, c) + abs(random.uniform(0, 0.02 * base))
        l = min(o, c) - abs(random.uniform(0, 0.02 * base))
        v = round(random.uniform(0.1, 5000.0), 4)
        ts = (t_now - (limit - i) * interval_seconds) * 1000
        candles.append({"ts": ts, "open": round(o, 8 if base < 1 else 2), "high": round(h, 8 if base < 1 else 2), "low": round(l, 8 if base < 1 else 2), "close": round(c, 8 if base < 1 else 2), "volume": v})
    return candles

def pretty_price(p: float) -> str:
    """Return price formatted with appropriate decimals."""
    return f"{p:.8f}" if p < 1 else f"{p:.2f}"

# ---------------------------------------------------------------------------
# Root / Health endpoint (simple)
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    return {"status": "ok", "service": "Blockflow Expanded Backend", "timestamp": now_ms()}

# ---------------------------------------------------------------------------
# Auth endpoints: register & login (very permissive demo)
# ---------------------------------------------------------------------------
@app.post("/register", response_model=dict)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    """
    Register route: creates a user in the DB and returns a JWT access token.
    For demo: password is not validated or hashed — replace with proper security in prod.
    """
    if models is None:
        logger.error("Attempt to register user but models unavailable.")
        raise HTTPException(status_code=500, detail="Server models not available")
    logger.info("Registering user: %s", payload.username)
    existing = db.query(models.User).filter(models.User.username == payload.username).first()
    if existing:
        logger.debug("Registration failed: username exists.")
        raise HTTPException(status_code=400, detail="Username already exists")
    # Save user
    user = models.User(username=payload.username, email=payload.email, balance=100000.0)
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        logger.exception("DB error creating user: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create user")
    token = create_access_token({"user_id": user.id})
    logger.info("User created: %s (id=%s)", user.username, user.id)
    return {"id": user.id, "username": user.username, "email": user.email, "access_token": token}

@app.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Login route: demo-only authentication that accepts any password if username exists.
    Returns a JWT token.
    """
    if models is None:
        logger.error("Attempt to login but models unavailable.")
        raise HTTPException(status_code=500, detail="Server models not available")
    logger.debug("Login attempt: %s", form_data.username)
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user:
        logger.debug("Login failed: user not found.")
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    token = create_access_token({"user_id": user.id})
    logger.info("User logged in: %s", user.username)
    return {"access_token": token, "token_type": "bearer"}

@app.get("/users")
def list_users(db: Session = Depends(get_db)):
    """
    Return a list of users. Demo endpoint; in production restrict to admin.
    """
    if models is None:
        logger.error("Users endpoint called but models not available.")
        raise HTTPException(status_code=500, detail="Server models not available")
    users = db.query(models.User).all()
    return [{"id": u.id, "username": u.username, "email": getattr(u, "email", None), "balance": getattr(u, "balance", None)} for u in users]

# ---------------------------------------------------------------------------
# P2P helpers: payload generator + endpoints
# ---------------------------------------------------------------------------
def _get_p2p_orders_payload(db: Session) -> List[Dict[str, Any]]:
    """
    Helper to fetch all P2P orders and attach username for convenience.
    """
    if models is None:
        return []
    orders = db.query(models.P2POrder).all()
    users = db.query(models.User).all()
    user_map = {u.id: u.username for u in users}
    payload = []
    for o in orders:
        payload.append({
            "id": o.id,
            "user_id": o.user_id,
            "merchant": o.merchant,
            "type": o.type,
            "price": o.price,
            "available": o.available,
            "limit_min": o.limit_min,
            "limit_max": o.limit_max,
            "payment_method": o.payment_method,
            "created_at": getattr(o, "created_at", None),
            "username": user_map.get(o.user_id, "Unknown")
        })
    return payload

@app.get("/p2p/orders")
def list_p2p_orders(db: Session = Depends(get_db)):
    """
    Returns all P2P orders. Orders are sorted by type then price for simple UX.
    """
    if models is None:
        logger.error("list_p2p_orders called but models unavailable.")
        raise HTTPException(status_code=500, detail="Server models not available")
    orders = db.query(models.P2POrder).order_by(models.P2POrder.type.desc(), models.P2POrder.price.desc()).all()
    logger.debug("Listing %d P2P orders", len(orders))
    return orders

@app.post("/p2p/orders")
def create_p2p_order(req: P2POrderRequest, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Creates a P2P order owned by the authenticated user.
    Broadcasts both a single 'order_update' and a 'order_list' snapshot.
    """
    logger.info("User %s creating P2P order: %s %s @ %s", getattr(current_user, "username", "unknown"), req.type, req.available, req.price)
    if req.price <= 0 or req.available <= 0:
        logger.debug("Invalid P2P order payload: price/available must be > 0")
        raise HTTPException(status_code=422, detail="Price and available must be > 0")

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
    try:
        db.add(order)
        db.commit()
        db.refresh(order)
    except Exception as e:
        db.rollback()
        logger.exception("Failed to create P2P order: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create order")

    # Non-blocking broadcasts
    asyncio.create_task(manager.broadcast({
        "type": "order_update",
        "action": "created",
        "order": {
            "id": order.id,
            "user_id": order.user_id,
            "merchant": order.merchant,
            "type": order.type,
            "price": order.price,
            "available": order.available,
            "limit_min": order.limit_min,
            "limit_max": order.limit_max,
            "payment_method": order.payment_method,
            "username": current_user.username
        }
    }))

    asyncio.create_task(manager.broadcast({
        "type": "order_list",
        "orders": _get_p2p_orders_payload(db)
    }))

    logger.info("P2P order created: id=%s by user=%s", order.id, current_user.username)
    return {"id": order.id, "user_id": order.user_id, "price": order.price, "available": order.available}

@app.delete("/p2p/orders/{order_id}")
def delete_p2p_order(order_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Deletes a P2P order. Only the owner may delete.
    Broadcasts deletion and order list snapshot.
    """
    logger.info("User %s requested deletion of order %s", current_user.username, order_id)
    order = db.query(models.P2POrder).filter(models.P2POrder.id == order_id).first()
    if not order:
        logger.debug("Order %s not found.", order_id)
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id:
        logger.debug("User %s not authorized to delete order %s", current_user.username, order_id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    try:
        db.delete(order)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("Error deleting order %s: %s", order_id, e)
        raise HTTPException(status_code=500, detail="Failed to delete order")

    asyncio.create_task(manager.broadcast({"type": "order_update", "action": "deleted", "order_id": order_id}))
    asyncio.create_task(manager.broadcast({"type": "order_list", "orders": _get_p2p_orders_payload(db)}))
    logger.info("Order %s deleted by user %s", order_id, current_user.username)
    return {"message": "Order deleted successfully"}

@app.post("/p2p/trade")
def execute_trade(req: P2PTradeExecutionRequest, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Execute a P2P trade between order owner and taker (authenticated user).
    Performs simple balance updates and records a Trade.
    Emits multiple broadcasts: trade_executed, balance_update, order_list.
    """
    logger.info("User %s attempting to execute trade on order %s amount=%s", current_user.username, req.order_id, req.amount)
    if current_user.id != req.taker_id:
        logger.debug("Taker ID %s does not match authenticated user %s", req.taker_id, current_user.id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Taker ID mismatch")

    order = db.query(models.P2POrder).filter(models.P2POrder.id == req.order_id).first()
    if not order:
        logger.debug("Order %s not found", req.order_id)
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id == current_user.id:
        logger.debug("User %s attempted to trade on own order", current_user.username)
        raise HTTPException(status_code=400, detail="Cannot trade against your own order")
    if req.amount <= 0 or req.amount > order.available:
        logger.debug("Invalid trade amount: %s vs available %s", req.amount, order.available)
        raise HTTPException(status_code=422, detail="Invalid trade amount")

    # Determine buyer and seller depending on order type
    if order.type.lower() == "sell":
        seller = db.query(models.User).filter(models.User.id == order.user_id).first()
        buyer = db.query(models.User).filter(models.User.id == req.taker_id).first()
    else:
        buyer = db.query(models.User).filter(models.User.id == order.user_id).first()
        seller = db.query(models.User).filter(models.User.id == req.taker_id).first()

    if not buyer or not seller:
        logger.debug("Buyer or seller not found during trade execution.")
        raise HTTPException(status_code=404, detail="Buyer or seller not found")

    total_value = order.price * req.amount
    if buyer.balance < total_value:
        logger.debug("Buyer %s has insufficient balance: %s < %s", buyer.username, buyer.balance, total_value)
        raise HTTPException(status_code=422, detail="Buyer's balance insufficient")

    # Apply balance updates atomically (DB will commit once)
    buyer.balance -= total_value
    seller.balance += total_value
    order.available -= req.amount
    filled = order.available <= 1e-9
    try:
        # Save trade record
        trade = models.Trade(buyer_id=buyer.id, seller_id=seller.id, price=order.price, amount=req.amount)
        db.add(trade)
        if filled:
            db.delete(order)
        db.commit()
        db.refresh(buyer)
        db.refresh(seller)
        db.refresh(trade)
    except Exception as e:
        db.rollback()
        logger.exception("DB error executing trade: %s", e)
        raise HTTPException(status_code=500, detail="Trade execution failed")

    # Fire broadcasts (non-blocking)
    asyncio.create_task(manager.broadcast({
        "type": "trade_executed",
        "trade": {"id": trade.id, "buyer_id": trade.buyer_id, "seller_id": trade.seller_id, "price": trade.price, "amount": trade.amount}
    }))
    asyncio.create_task(manager.broadcast({
        "type": "balance_update",
        "users": [
            {"id": buyer.id, "username": buyer.username, "balance": buyer.balance},
            {"id": seller.id, "username": seller.username, "balance": seller.balance}
        ]
    }))
    asyncio.create_task(manager.broadcast({"type": "order_list", "orders": _get_p2p_orders_payload(db)}))

    logger.info("Trade executed: id=%s amount=%s price=%s", trade.id, trade.amount, trade.price)
    return {"trade_id": trade.id, "buyer_balance": buyer.balance, "seller_balance": seller.balance}

# ---------------------------------------------------------------------------
# Spot / Margin / Futures / Options prototype endpoints (DB-backed)
# ---------------------------------------------------------------------------
# These endpoints are simple wrappers that persist demo trades to the DB using
# the models you provide (SpotTrade, MarginTrade, FuturesUsdmTrade, etc.).
# If those models don't exist in your models.py, these endpoints will raise.
@app.post("/spot/trade")
def place_spot_trade(trade: ExchangeTradeRequest, db: Session = Depends(get_db)):
    logger.debug("Placing spot trade: %s", trade.dict())
    new_trade = models.SpotTrade(**trade.dict())
    db.add(new_trade)
    db.commit()
    db.refresh(new_trade)
    logger.info("Spot trade stored id=%s", new_trade.id)
    return new_trade

@app.get("/spot/orders")
def list_spot_orders(db: Session = Depends(get_db)):
    return db.query(models.SpotTrade).all()

@app.post("/margin/trade")
def place_margin_trade(trade: ExchangeTradeRequest, db: Session = Depends(get_db)):
    new_trade = models.MarginTrade(**trade.dict())
    db.add(new_trade)
    db.commit()
    db.refresh(new_trade)
    return new_trade

@app.get("/margin/orders")
def list_margin_orders(db: Session = Depends(get_db)):
    return db.query(models.MarginTrade).all()

@app.post("/futures/usdm/trade")
def place_usdm_futures_trade(trade: ExchangeTradeRequest, db: Session = Depends(get_db)):
    new_trade = models.FuturesUsdmTrade(**trade.dict())
    db.add(new_trade)
    db.commit()
    db.refresh(new_trade)
    return new_trade

@app.get("/futures/usdm/orders")
def list_usdm_futures_orders(db: Session = Depends(get_db)):
    return db.query(models.FuturesUsdmTrade).all()

@app.post("/futures/coinm/trade")
def place_coinm_futures_trade(trade: ExchangeTradeRequest, db: Session = Depends(get_db)):
    new_trade = models.FuturesCoinmTrade(**trade.dict())
    db.add(new_trade)
    db.commit()
    db.refresh(new_trade)
    return new_trade

@app.get("/futures/coinm/orders")
def list_coinm_futures_orders(db: Session = Depends(get_db)):
    return db.query(models.FuturesCoinmTrade).all()

@app.post("/options/trade")
def place_options_trade(trade: ExchangeTradeRequest, db: Session = Depends(get_db)):
    new_trade = models.OptionsTrade(**trade.dict())
    db.add(new_trade)
    db.commit()
    db.refresh(new_trade)
    return new_trade

@app.get("/options/orders")
def list_options_orders(db: Session = Depends(get_db)):
    return db.query(models.OptionsTrade).all()

# ---------------------------------------------------------------------------
# CoinGecko poller + auto-sync for P2P orders (resilient + jitter)
# ---------------------------------------------------------------------------
async def fetch_prices_from_coingecko():
    """
    Single-shot fetch from CoinGecko simple price API.
    Returns parsed JSON like: {"bitcoin":{"usd":..., "inr":...}, "ethereum": {...}}
    """
    url = "https://api.coingecko.com/api/v3/simple/price"
    headers = {}
    if COINGECKO_API_KEY:
        headers["x-cg-pro-api-key"] = COINGECKO_API_KEY
    params = {"ids": "bitcoin,ethereum", "vs_currencies": "usd,inr"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        logger.debug("CoinGecko response status: %s", resp.status_code)
        return resp.json()

async def broadcast_price_data(data: Dict[str, Any]):
    """
    Convert coin-gecko style payload into our internal price_update messages and broadcast.
    """
    symbols_map = {"bitcoin": "BTC/USDT", "ethereum": "ETH/USDT"}
    for cg_id, sym in symbols_map.items():
        usd_price = data.get(cg_id, {}).get("usd")
        inr_price = data.get(cg_id, {}).get("inr")
        if usd_price is not None and inr_price is not None:
            payload = {"type": "price_update", "symbol": sym, "usd": usd_price, "inr": inr_price, "timestamp": now_ms()}
            logger.debug("Broadcasting price_update: %s %s", sym, usd_price)
            await manager.broadcast(payload)

def sync_update_p2p_orders(db: Session, btc_inr_price: float):
    """
    Synchronous (blocking) DB update runner to adjust P2P order prices in response to live price.
    This is intentionally synchronous so it can be run via asyncio.to_thread for safety.
    """
    if models is None:
        logger.warning("sync_update_p2p_orders called but models not available.")
        return
    orders = db.query(models.P2POrder).all()
    updated_count = 0
    SELL_MARKUP = 1.015  # +1.5%
    BUY_DISCOUNT = 0.985  # -1.5%
    logger.debug("Syncing %d P2P orders to BTC INR price: %s", len(orders), btc_inr_price)
    for order in orders:
        new_price = None
        if order.type == "Sell":
            new_price = btc_inr_price * SELL_MARKUP
        elif order.type == "Buy":
            new_price = btc_inr_price * BUY_DISCOUNT
        if new_price is not None:
            order.price = round(new_price, 0)
            db.add(order)
            updated_count += 1
    db.commit()
    if updated_count > 0:
        logger.info("Auto-synced %d P2P orders to new BTC price: ₹%s", updated_count, int(btc_inr_price))

def sync_seed_demo_data(db: Session):
    """
    Create a demo user and some orders/trades if none exist.
    This runs synchronously on startup via asyncio.to_thread to avoid blocking the startup event loop.
    """
    if models is None:
        logger.warning("sync_seed_demo_data called but models not available.")
        return
    # Create demo user
    demo_user = db.query(models.User).filter_by(username="demo_user").first()
    if not demo_user:
        demo_user = models.User(username="demo_user", email="demo@blockflow.com", balance=100000.0)
        db.add(demo_user)
        db.commit()
        db.refresh(demo_user)
        logger.info("Created demo_user (id=%s)", demo_user.id)
    # Seed P2P orders if none
    existing_orders = db.query(models.P2POrder).count()
    if existing_orders == 0:
        demo_orders = [
            models.P2POrder(user_id=demo_user.id, merchant="Blockflow Merchant", type="Buy", price=49500, available=0.05, limit_min=500, limit_max=2000, payment_method="UPI"),
            models.P2POrder(user_id=demo_user.id, merchant="Blockflow Merchant", type="Sell", price=50500, available=0.08, limit_min=1000, limit_max=5000, payment_method="Bank Transfer"),
        ]
        db.add_all(demo_orders)
        db.commit()
        logger.info("Seeded %d demo P2P orders", len(demo_orders))
    else:
        logger.debug("P2P demo orders already exist: %d", existing_orders)
    # Ensure at least one trade exists
    existing_trades = db.query(models.Trade).count()
    if existing_trades == 0:
        # Create a dummy trade if possible (requires two users)
        users = db.query(models.User).limit(2).all()
        if len(users) >= 2:
            t = models.Trade(buyer_id=users[0].id, seller_id=users[1].id, price=50000, amount=0.01)
            db.add(t)
            db.commit()
            logger.info("Seeded a demo trade (id=%s)", t.id)
    logger.info("Demo data seeding complete.")

async def coingecko_price_poller():
    """
    Background task that:
     - Polls CoinGecko every POLL_TICK_INTERVAL * POLL_INTERVAL_TICKS seconds (default 30s),
     - Broadcasts jittered prices every POLL_TICK_INTERVAL seconds,
     - Auto-syncs P2P orders at the poll interval,
     - Falls back to a cached demo dataset when API fails/rate-limited.
    """
    cache = {
        "bitcoin": {"usd": 50000.00, "inr": 4200000.00},
        "ethereum": {"usd": 3000.00, "inr": 250000.00}
    }
    tick_count = 0
    failures = 0
    demo_mode = False

    logger.info("CoinGecko poller started: tick_interval=%s, poll_ticks=%s", POLL_TICK_INTERVAL, POLL_INTERVAL_TICKS)

    while True:
        # Full poll every POLL_INTERVAL_TICKS ticks
        if tick_count % POLL_INTERVAL_TICKS == 0:
            try:
                new_data = await fetch_prices_from_coingecko()
                # Validate structure & shallow copy
                if isinstance(new_data, dict):
                    cache = new_data
                    failures = 0
                    demo_mode = False
                    logger.info("Updated prices from CoinGecko at %s", time.strftime("%H:%M:%S"))
                else:
                    raise ValueError("Invalid CoinGecko response structure")
            except Exception as e:
                failures += 1
                logger.warning("CoinGecko fetch failure (%d): %s", failures, e)
                if failures > MAX_CG_FAILURES or "429" in str(e):
                    if not demo_mode:
                        logger.error("Switching to DEMO mode due to repeated CoinGecko failures.")
                        demo_mode = True
        # jitter prices for liveliness
        jittered = {}
        for k, v in cache.items():
            jittered[k] = {cur: round(price * (1 + random.uniform(-0.0015, 0.0015)), 2) for cur, price in v.items()}
        # broadcast each mapped symbol
        await broadcast_price_data(jittered)
        # every poll tick also attempt to auto-sync P2P prices
        if tick_count % POLL_INTERVAL_TICKS == 0:
            btc_inr = jittered.get("bitcoin", {}).get("inr")
            if btc_inr is not None and models is not None:
                db = SessionLocal()
                try:
                    await asyncio.to_thread(sync_update_p2p_orders, db, btc_inr)
                    await manager.broadcast({"type": "orders_refresh"})
                finally:
                    db.close()
        tick_count += 1
        await asyncio.sleep(POLL_TICK_INTERVAL)

# ---------------------------------------------------------------------------
# WebSocket endpoints: app-wide and market simulator
# ---------------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Simple app-wide websocket to receive pings and broadcast server messages.
    Clients may send "ping" to receive a "pong" with timestamp.
    All other messages are ignored for now.
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            logger.debug("Received ws message from client: %s", data)
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong", "ts": now_ms()}))
            else:
                # Echo small ack for other messages to keep connection lively
                await websocket.send_text(json.dumps({"type": "ack", "msg": "received", "ts": now_ms()}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.exception("Error in /ws endpoint: %s", e)
        manager.disconnect(websocket)

@app.websocket("/ws/market")
async def ws_market(ws: WebSocket):
    """
    Market simulator websocket. Broadcasts:
      - ticker messages (every tick)
      - trade messages (frequent)
      - occasional orderbook snapshots
    This is intended for frontend dev to consume so TradingView + orderbooks look realistic.
    """
    await manager.connect(ws)
    try:
        while True:
            symbol = random.choice(list(SYMBOLS.keys()))
            base = SYMBOLS.get(symbol, BASE_PRICE)
            # Step price with small jitter + random shock occasionally
            shock = 0
            if random.random() < 0.02:
                # occasional micro shock to make chart show spikes
                shock = random.uniform(-0.02 * base, 0.02 * base)
            price = round(jitter(base, pct=0.001) + random.uniform(-0.005 * base, 0.005 * base) + shock, 8 if base < 1 else 2)
            SYMBOLS[symbol] = price
            # ticker
            ticker = {"type": "ticker", "symbol": symbol, "price": price, "ts": now_ms()}
            await manager.broadcast_json(ticker)
            # trades (frequent)
            if random.random() < 0.85:
                trade_msg = {
                    "type": "trade",
                    "symbol": symbol,
                    "price": round(price + random.uniform(-0.002 * price, 0.002 * price), 8 if price < 1 else 2),
                    "qty": round(random.uniform(0.0001, 12.0), 6),
                    "side": random.choice(["buy", "sell"]),
                    "ts": now_ms()
                }
                await manager.broadcast_json(trade_msg)
            # occasional orderbook snapshot
            if random.random() < 0.12:
                bids, asks = gen_orderbook(price, depth=12, spread_min=0.1, spread_max=3.5)
                ob = {"type": "orderbook", "symbol": symbol, "bids": bids, "asks": asks, "seq": now_ms()}
                await manager.broadcast_json(ob)
            # Sleep a short random time to create natural cadence
            await asyncio.sleep(random.uniform(0.6, 1.8))
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception as e:
        logger.exception("Error in /ws/market websocket: %s", e)
        manager.disconnect(ws)

# ---------------------------------------------------------------------------
# Spot REST endpoints - orderbook, candles, trades, place trade, helpers
# ---------------------------------------------------------------------------
@app.get("/api/market/orderbook")
async def api_orderbook(symbol: str = Query("BTCUSDT"), limit: int = Query(50)):
    """
    Return a synthetic orderbook for the requested symbol.
    Good for populating level-2 UI.
    """
    base = SYMBOLS.get(symbol, BASE_PRICE)
    depth = min(max(10, limit), 500)
    bids, asks = gen_orderbook(base, depth=depth, spread_min=0.05, spread_max=4.0)
    logger.debug("Generated orderbook for %s depth=%s", symbol, depth)
    return {"bids": bids, "asks": asks, "seq": now_ms()}

@app.get("/api/market/candles")
async def api_candles(symbol: str = Query("BTCUSDT"), interval: str = Query("1m"), limit: int = Query(200)):
    """
    Returns a list of candles suitable for a TradingView fallback.
    `interval` accepted but not deeply validated in demo.
    """
    base = SYMBOLS.get(symbol, BASE_PRICE)
    # parse interval string to seconds (basic support)
    interval_seconds = 60
    if interval.endswith("m"):
        try:
            interval_seconds = int(interval[:-1]) * 60
        except Exception:
            interval_seconds = 60
    elif interval.endswith("h"):
        try:
            interval_seconds = int(interval[:-1]) * 3600
        except Exception:
            interval_seconds = 3600
    # limit safety
    limit = min(max(10, limit), 2000)
    candles = gen_candles(base, interval_seconds=interval_seconds, limit=limit)
    logger.debug("Generated %d candles for %s @ interval %s", len(candles), symbol, interval)
    return candles

@app.get("/api/market/trades")
async def api_trades(symbol: str = Query("BTCUSDT"), limit: int = Query(100)):
    """
    Return a recent trades history list for front-end trade feed.
    """
    base = SYMBOLS.get(symbol, BASE_PRICE)
    limit = min(max(10, limit), 500)
    trades = gen_trades_history(symbol, base, limit=limit)
    logger.debug("Generated %d trades for %s", len(trades), symbol)
    return trades

class PlaceOrderReq(BaseModel):
    symbol: str
    side: str  # 'buy' | 'sell'
    type: str  # 'market' | 'limit'
    qty: float
    price: Optional[float] = None
    tp: Optional[float] = None
    sl: Optional[float] = None

@app.post("/api/trade/place")
async def api_trade_place(req: PlaceOrderReq):
    """
    Mock trade placement endpoint. Simulates an immediate fill for demo.
    Broadcasts a 'trade' message so frontends see fills in the trade feed.
    """
    # Simulate small backend latency
    await asyncio.sleep(random.uniform(0.06, 0.4))
    avg_price = req.price if req.price is not None else round(SYMBOLS.get(req.symbol, BASE_PRICE) + random.uniform(-0.003 * BASE_PRICE, 0.003 * BASE_PRICE), 8 if SYMBOLS.get(req.symbol, BASE_PRICE) < 1 else 2)
    resp = {
        "symbol": req.symbol,
        "side": req.side,
        "qty": req.qty,
        "avgPrice": round(avg_price, 8 if avg_price < 1 else 2),
        "status": "FILLED",
        "tp": req.tp,
        "sl": req.sl,
        "txHash": f"0x{random.randint(10**8, 10**16):x}",
        "ledgerSeq": random.randint(100000, 999999),
        "timestamp": now_ms(),
    }
    # Broadcast the fill
    await manager.broadcast_json({"type": "trade", "symbol": req.symbol, "price": resp["avgPrice"], "qty": req.qty, "side": req.side, "ts": resp["timestamp"]})
    logger.info("Placed mock trade: %s %s %s @ %s", req.side, req.qty, req.symbol, resp["avgPrice"])
    return resp

@app.get("/api/ping")
async def api_ping():
    """
    Simple latency / health helper for frontend. Returns server timestamp.
    """
    return {"ok": True, "ts": now_ms()}

@app.get("/api/trade/pnl")
async def api_pnl(entry: float = Query(...), mark: float = Query(...), size: float = Query(...), side: str = Query("long")):
    """
    Quick PnL calculator. Useful for displaying floating pnl in UI.
    """
    if side not in ("long", "short"):
        side = "long"
    pnl = (mark - entry) * size if side == "long" else (entry - mark) * size
    percent = (pnl / (entry * size)) * 100 if (entry * size) != 0 else 0.0
    logger.debug("PnL calc entry=%s mark=%s size=%s side=%s -> pnl=%s percent=%s", entry, mark, size, side, pnl, percent)
    return {"pnl": round(pnl, 8), "percent": round(percent, 6)}

# ---------------------------------------------------------------------------
# Startup tasks: seed DB and start coin-gecko poller
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def start_background_tasks():
    """
    Startup handler:
      - seeds demo data (in a thread)
      - launches coin-gecko poller in background
    """
    logger.info("Application startup: seeding demo data and starting background poller.")
    if models is None:
        logger.warning("Models are not available; skipping demo seeding.")
    else:
        # Run synchronous seed in a thread to avoid blocking event loop
        db = SessionLocal()
        try:
            await asyncio.to_thread(sync_seed_demo_data, db)
        finally:
            db.close()
    # Start poller (background task)
    asyncio.create_task(coingecko_price_poller())
    logger.info("Background tasks started: CoinGecko poller launched.")

# ---------------------------------------------------------------------------
# If executed directly, run with uvicorn
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    logger.info("Launching uvicorn for main:app")
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)

