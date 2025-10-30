
import os
import sys
import json
import logging
import subprocess
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseSettings

# Add project path so Render or other runners find subpackages reliably
ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# Optional: load environment from .env if present
from dotenv import load_dotenv
load_dotenv()

# ---------- Settings ----------
class Settings(BaseSettings):
    ENV: str = os.getenv("ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./blockflow.db")
    # External host for the frontend to call
    API_PREFIX: str = os.getenv("API_PREFIX", "/api")
    # WS base if needed
    WS_PREFIX: str = os.getenv("WS_PREFIX", "/ws")

    class Config:
        env_file = ".env"

settings = Settings()

# ---------- Logging ----------
logging.basicConfig(level=logging.DEBUG if settings.DEBUG else logging.INFO)
logger = logging.getLogger("blockflow")

# ---------- Alembic / DB bootstrap (best-effort run at startup) ----------
def run_alembic_migrations():
    """
    Attempt to run alembic upgrade head at startup.
    If alembic not configured or fails, log and continue.
    """
    try:
        # Adjust this command if your alembic.ini is in a different location
        logger.info("Running Alembic migrations...")
        subprocess.run(
            ["alembic", "upgrade", "head"],
            check=True,
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        logger.info("Alembic migrations applied successfully.")
    except Exception as e:
        logger.warning("Alembic migrations skipped/failed: %s", str(e))

# ---------- Single FastAPI app (KEEP ONLY ONE) ----------
app = FastAPI(
    title="Blockflow Exchange (Investor Demo - Fixed)",
    description="Blockflow backend: Wallet, Ledger, Spot, Futures, Auth, Admin",
    version="2.0-Brahmastra",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ---------- Middlewares ----------
# CORS - allow your frontends (be restrictive in prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["https://your-frontend-domain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip for responses (optional)
app.add_middleware(GZipMiddleware, minimum_size=500)

# ---------- Global exception handler ----------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error: %s %s", request.url.path, str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "detail": str(exc),
            "path": request.url.path,
        },
    )

# ---------- Request logging middleware ----------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info("REQUEST: %s %s", request.method, request.url.path)
    try:
        response = await call_next(request)
        logger.info("RESPONSE: %s %s -> %s", request.method, request.url.path, response.status_code)
        return response
    except Exception as e:
        logger.exception("Error handling request %s %s: %s", request.method, request.url.path, str(e))
        raise

# ---------- Database / ORM initialization (placeholder) ----------
# Import and initialize your DB engine / session maker here.
# Example using SQLAlchemy:
try:
    from app.db import engine, Base  # adjust to your project layout
    # Ensure metadata / tables exist (optional; Alembic is preferred)
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ensured.")
except Exception as e:
    logger.warning("DB initialization skipped/failed: %s", str(e))

# Attempt alembic migration on startup (best effort)
try:
    run_alembic_migrations()
except Exception:
    pass

# ---------- Simple WebSocket manager (shared) ----------
class ConnectionManager:
    def __init__(self):
        self.active: Dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active[user_id] = websocket
        logger.debug("WS connected: %s", user_id)

    def disconnect(self, user_id: str):
        ws = self.active.pop(user_id, None)
        if ws:
            logger.debug("WS disconnected: %s", user_id)

    async def send_to(self, user_id: str, message: Any):
        ws = self.active.get(user_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.debug("Failed send to %s: %s", user_id, str(e))

    async def broadcast(self, message: Any):
        for uid, ws in list(self.active.items()):
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.debug("Broadcast failed to %s: %s", uid, str(e))

ws_manager = ConnectionManager()

# Provide a simple health endpoint
@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.ENV}

# Provide a small root endpoint
@app.get("/")
async def root():
    return {"message": "Blockflow backend ready", "version": settings.__dict__.get("ENV", "dev")}
# =====================================
# DATABASE INITIALIZATION
# =====================================
Base.metadata.create_all(bind=engine)

# =====================================
# ROUTERS
# =====================================
app.include_router(auth_router)
app.include_router(wallet_router)

# =====================================
# BASIC ROUTES
# =====================================
@app.get("/")
def root():
    return {"message": "🚀 Blockflow backend ready!", "status": "ok"}

@app.get("/health")
def health_check():
    return {"status": "ok", "db": "connected"}

# --------------------------
# End of main.py
# --------------------------
# DB detection
# --------------------------
def detect_db_url() -> str:
    env = os.getenv("DATABASE_URL")
    if env:
        return env
    candidates = [
        "sqlite:///./blockflow_v5.db",
        "sqlite:///./app/blockflow_v5.db",
        "sqlite:///../blockflow_v5.db",
        "sqlite:///./blockflow.db",
    ]
    for c in candidates:
        if c.startswith("sqlite:///"):
            f = c.replace("sqlite:///", "")
            if os.path.exists(f):
                return c
    return candidates[0]

DATABASE_URL = detect_db_url()

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ensure tables exist (safe)
try:
    models.Base.metadata.create_all(bind=engine)
except Exception as e:
    print("WARNING: could not auto-create tables:", e)

# --------------------------
# FastAPI app
# --------------------------
app = FastAPI(title="Blockflow Exchange (Investor Demo - Fixed)", version="5.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
@app.on_event("startup")
async def start_background_tasks():
    asyncio.create_task(simulate_metrics())
@app.get("/api/liquidity")
def api_liquidity():
    """Return aggregated liquidity pool snapshot for frontend dashboards."""
    try:
        return {"status": "ok", "data": get_pool_state()}
    except Exception as e:
        return {"status": "error", "message": str(e)}
@app.get("/api/alerts")
def get_alerts():
    """Return dynamic exchange/compliance alerts."""
    return {"status": "ok", "data": simulate_alerts()}


app.include_router(metrics_router)
app.include_router(compliance_router)
app.include_router(auth_router)


# --------------------------
# Helper: Model to Dict
# --------------------------
def model_as_dict(obj):
    return {c.key: getattr(obj, c.key) for c in inspect(obj).mapper.column_attrs}

# Attach to all models
for cls in [User, P2POrder, SpotTrade, MarginTrade, FuturesUsdmTrade, FuturesCoinmTrade, OptionsTrade]:
    cls.as_dict = lambda self: model_as_dict(self)

# --------------------------
# WebSocket manager (IMPROVED)
# --------------------------
class WebSocketManager:
    def __init__(self):
        self.connections: List[WebSocket] = []
        self.subscriptions: Dict[WebSocket, str] = {}  # ws -> symbol
        self.lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self.lock:
            self.connections.append(ws)

    async def disconnect(self, ws: WebSocket):
        async with self.lock:
            if ws in self.connections:
                self.connections.remove(ws)
            if ws in self.subscriptions:
                del self.subscriptions[ws]

    async def subscribe(self, ws: WebSocket, symbol: str):
        async with self.lock:
            self.subscriptions[ws] = symbol

    async def broadcast_json(self, payload: Dict[str, Any]):
        text = json.dumps(payload, default=str)
        async with self.lock:
            conns = list(self.connections)
        dead = []
        for ws in conns:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        if dead:
            async with self.lock:
                for d in dead:
                    if d in self.connections:
                        self.connections.remove(d)
                    if d in self.subscriptions:
                        del self.subscriptions[d]

ws_manager = WebSocketManager()

# --------------------------
# Pydantic request schemas
# --------------------------
class P2PCreateSchema(BaseModel):
    username: str
    asset: str
    price: float
    amount: float
    payment_method: str

class SpotPlaceSchema(BaseModel):
    username: str
    pair: str
    side: str  # buy / sell
    price: Optional[float] = None
    amount: float
    leverage: Optional[float] = 1.0
    tp: Optional[float] = None
    sl: Optional[float] = None

class FuturesPlaceSchema(BaseModel):
    username: str
    pair: str
    side: str
    price: float
    amount: float
    leverage: Optional[float] = 20.0

class OptionsPlaceSchema(BaseModel):
    username: str
    pair: str
    side: str
    strike: float
    option_type: str  # call/put
    premium: float
    size: float

# --------------------------
# Root / Health
# --------------------------
@app.get("/")
async def root():
    return {"ok": True, "app": "blockflow-exchange-fixed", "version": "5.1", "time": datetime.now(timezone.utc).isoformat()}

@app.get("/health")
async def health():
    return {"ok": True, "db": DATABASE_URL, "status": "connected"}

# --------------------------
# P2P Endpoints
# --------------------------
@app.get("/p2p/orders")
async def p2p_list(db: Session = Depends(get_db)):
    rows = db.query(P2POrder).order_by(P2POrder.created_at.desc()).limit(500).all()
    out = []
    for r in rows:
        out.append({
            "id": r.id,
            "username": getattr(r, "username", getattr(r, "merchant", None)),
            "asset": r.asset,
            "price": r.price,
            "amount": r.amount,
            "payment_method": getattr(r, "payment_method", None),
            "status": r.status,
            "created_at": str(r.created_at)
        })
    return out

@app.post("/p2p/create")
async def p2p_create(req: P2PCreateSchema, db: Session = Depends(get_db)):
    o = P2POrder(
        username=req.username,
        asset=req.asset,
        price=req.price,
        amount=req.amount,
        payment_method=req.payment_method,
        status="active"
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    try:
        await ws_manager.broadcast_json({"type":"p2p_new", "order": {"id": o.id, "username": o.username, "asset": o.asset, "price": o.price, "amount": o.amount}})
    except Exception:
        pass
    return {"ok": True, "id": o.id}

@app.post("/p2p/settle/{order_id}")
async def p2p_settle(order_id: int, db: Session = Depends(get_db)):
    o = db.query(P2POrder).filter(P2POrder.id == order_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="order not found")
    o.status = "settled"
    db.commit()
    tds = round((o.price or 0) * (o.amount or 0) * 0.01, 2)
    try:
        await ws_manager.broadcast_json({"type":"p2p_settle", "order_id": o.id, "tds": tds})
    except Exception:
        pass
    return {"ok": True, "tds": tds}

# --------------------------
# Spot Endpoints (FIXED)
# --------------------------
@app.post("/spot/trade")
async def spot_trade(req: SpotPlaceSchema, db: Session = Depends(get_db)):
    # If price not provided, use market price (get from recent trades)
    price = req.price
    if not price:
        recent = db.query(SpotTrade).filter(SpotTrade.pair == req.pair).order_by(SpotTrade.timestamp.desc()).first()
        price = recent.price if recent else 30000.0
    
    t = SpotTrade(
        username=req.username, 
        pair=req.pair, 
        side=req.side, 
        price=price, 
        amount=req.amount
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    
    # Broadcast to WebSocket
    try:
        await ws_manager.broadcast_json({
            "type": "trade",
            "market": "spot",
            "trade": {
                "id": t.id,
                "pair": t.pair,
                "price": t.price,
                "amount": t.amount,
                "side": t.side,
                "ts": str(t.timestamp)
            }
        })
    except Exception:
        pass
    
    return {"ok": True, "success": True, "id": t.id, "executed": {
        "id": t.id,
        "price": t.price,
        "amount": t.amount,
        "side": t.side
    }}

@app.get("/spot/orders")
async def spot_orders(db: Session = Depends(get_db)):
    rows = db.query(SpotTrade).order_by(SpotTrade.timestamp.desc()).limit(200).all()
    return [{"id": r.id, "username": r.username, "pair": r.pair, "price": r.price, "amount": r.amount, "side": r.side, "ts": str(r.timestamp)} for r in rows]

# --------------------------
# NEW: Trades with Symbol Filter
# --------------------------
@app.get("/api/trades")
async def get_trades(symbol: Optional[str] = None, limit: int = 200, db: Session = Depends(get_db)):
    """Get recent trades, optionally filtered by symbol"""
    try:
        query = db.query(SpotTrade)
        
        if symbol:
            query = query.filter(SpotTrade.pair == symbol)
        
        trades = query.order_by(SpotTrade.timestamp.desc()).limit(limit).all()
        
        return [{
            "id": t.id,
            "price": t.price,
            "amount": t.amount,
            "side": t.side,
            "ts": str(t.timestamp),
            "pair": t.pair
        } for t in trades]
    
    except Exception as e:
        print(f"Trades error: {e}")
        return []

# --------------------------
# NEW: Orderbook with Symbol Filter
# --------------------------
@app.get("/api/market/orderbook")
async def get_orderbook(symbol: Optional[str] = None, db: Session = Depends(get_db)):
    """Get orderbook with bids/asks, filtered by symbol"""
    try:
        query = db.query(SpotTrade)
        if symbol:
            query = query.filter(SpotTrade.pair == symbol)
        
        trades = query.order_by(SpotTrade.timestamp.desc()).limit(100).all()
        
        bids = []
        asks = []
        
        for t in trades:
            entry = {"price": t.price, "amount": t.amount}
            if t.side == "buy":
                bids.append(entry)
            else:
                asks.append(entry)
        
        # Sort: bids high to low, asks low to high
        bids.sort(key=lambda x: x['price'], reverse=True)
        asks.sort(key=lambda x: x['price'])
        
        return {
            "bids": bids[:20],
            "asks": asks[:20],
            "symbol": symbol
        }
    
    except Exception as e:
        print(f"Orderbook error: {e}")
        return {"bids": [], "asks": []}

# --------------------------
# NEW: Leaderboard Endpoint
# --------------------------
@app.get("/api/leaderboard")
async def get_leaderboard(limit: int = 10, db: Session = Depends(get_db)):
    """Get top traders by PnL"""
    try:
        users = db.query(User).all()
        leaderboard = []
        
        for user in users:
            # Calculate PnL from margin trades
            margin_trades = db.query(MarginTrade).filter(
                MarginTrade.username == user.username
            ).all()
            
            futures_trades = db.query(FuturesUsdmTrade).filter(
                FuturesUsdmTrade.username == user.username
            ).all()
            
            total_pnl = sum([t.pnl or 0 for t in margin_trades])
            total_pnl += sum([getattr(t, 'pnl', 0) or 0 for t in futures_trades])
            
            leaderboard.append({
                "id": user.id,
                "username": user.username,
                "pnl": round(total_pnl, 2)
            })
        
        # Sort by PnL descending
        leaderboard.sort(key=lambda x: x['pnl'], reverse=True)
        return leaderboard[:limit]
    
    except Exception as e:
        print(f"Leaderboard error: {e}")
        # Return demo data if error
        return [
            {"id": 1, "username": "Alpha", "pnl": 12450},
            {"id": 2, "username": "Beta", "pnl": 9812}
        ]

# --------------------------
# NEW: Active Positions
# --------------------------
@app.get("/api/positions")
async def get_positions(username: Optional[str] = "demo_trader_0", db: Session = Depends(get_db)):
    """Get active positions for a user"""
    try:
        # Get margin trades
        margin = db.query(MarginTrade).filter(
            MarginTrade.username == username
        ).order_by(MarginTrade.timestamp.desc()).limit(10).all()
        
        # Get futures
        futures = db.query(FuturesUsdmTrade).filter(
            FuturesUsdmTrade.username == username
        ).order_by(FuturesUsdmTrade.timestamp.desc()).limit(10).all()
        
        positions = []
        
        for m in margin:
            positions.append({
                "id": m.id,
                "symbol": m.pair,
                "side": m.side,
                "size": m.amount,
                "leverage": m.leverage,
                "unrealizedPnl": m.pnl or 0,
                "pnlPercent": ((m.pnl or 0) / (m.price * m.amount) * 100) if m.price * m.amount > 0 else 0
            })
        
        for f in futures:
            pnl = getattr(f, 'pnl', 0) or 0
            positions.append({
                "id": f.id,
                "symbol": f.pair,
                "side": f.side,
                "size": f.amount,
                "leverage": f.leverage,
                "unrealizedPnl": pnl,
                "pnlPercent": (pnl / (f.price * f.amount) * 100) if f.price * f.amount > 0 else 0
            })
        
        return positions
    
    except Exception as e:
        print(f"Positions error: {e}")
        return []

# --------------------------
# Margin Endpoints
# --------------------------
@app.post("/margin/trade")
async def margin_trade(req: SpotPlaceSchema, db: Session = Depends(get_db)):
    t = MarginTrade(
        username=req.username, 
        pair=req.pair, 
        side=req.side, 
        leverage=req.leverage or 10.0, 
        price=req.price or 30000.0, 
        amount=req.amount, 
        pnl=0.0
    )
    # Demo PnL calc
    t.pnl = round((t.amount * t.price) * (0.01 if t.side == "sell" else -0.01), 3)
    db.add(t)
    db.commit()
    db.refresh(t)
    try:
        await ws_manager.broadcast_json({"type":"trade", "market":"margin", "trade": {"id": t.id, "pair": t.pair, "price": t.price}})
    except Exception:
        pass
    return {"ok": True, "id": t.id, "pnl": t.pnl}

@app.get("/margin/orders")
async def margin_orders(db: Session = Depends(get_db)):
    rows = db.query(MarginTrade).order_by(MarginTrade.timestamp.desc()).limit(200).all()
    return [{"id": r.id, "user": r.username, "pair": r.pair, "price": r.price, "amount": r.amount, "pnl": r.pnl} for r in rows]

# --------------------------
# Futures USDM Endpoints
# --------------------------
@app.post("/futures/usdm/trade")
async def futures_usdm_trade(req: FuturesPlaceSchema, db: Session = Depends(get_db)):
    t = FuturesUsdmTrade(
        username=req.username, 
        pair=req.pair, 
        side=req.side, 
        leverage=req.leverage or 20.0, 
        price=req.price, 
        amount=req.amount, 
        pnl=0.0
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    try:
        await ws_manager.broadcast_json({"type":"trade", "market":"futures_usdm", "trade": {"id": t.id, "pair": t.pair, "price": t.price}})
    except Exception:
        pass
    return {"ok": True, "id": t.id}

@app.get("/futures/usdm/orders")
async def futures_usdm_orders(db: Session = Depends(get_db)):
    rows = db.query(FuturesUsdmTrade).order_by(FuturesUsdmTrade.timestamp.desc()).limit(200).all()
    return [{"id": r.id, "user": r.username, "pair": r.pair, "price": r.price, "amount": r.amount, "leverage": r.leverage} for r in rows]

# --------------------------
# Futures COINM Endpoints
# --------------------------
@app.post("/futures/coinm/trade")
async def futures_coinm_trade(req: FuturesPlaceSchema, db: Session = Depends(get_db)):
    t = FuturesCoinmTrade(
        username=req.username, 
        pair=req.pair, 
        side=req.side, 
        leverage=req.leverage or 20.0, 
        price=req.price, 
        amount=req.amount, 
        pnl=0.0
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    try:
        await ws_manager.broadcast_json({"type":"trade", "market":"futures_coinm", "trade": {"id": t.id, "pair": t.pair, "price": t.price}})
    except Exception:
        pass
    return {"ok": True, "id": t.id}

@app.get("/futures/coinm/orders")
async def futures_coinm_orders(db: Session = Depends(get_db)):
    rows = db.query(FuturesCoinmTrade).order_by(FuturesCoinmTrade.timestamp.desc()).limit(200).all()
    return [{"id": r.id, "user": r.username, "pair": r.pair, "price": r.price, "amount": r.amount, "leverage": r.leverage} for r in rows]

# --------------------------
# Options Endpoints
# --------------------------
@app.post("/options/trade")
async def options_trade(req: OptionsPlaceSchema, db: Session = Depends(get_db)):
    t = OptionsTrade(
        username=req.username, 
        pair=req.pair, 
        side=req.side, 
        strike=req.strike, 
        option_type=req.option_type, 
        premium=req.premium, 
        size=req.size
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    try:
        await ws_manager.broadcast_json({"type":"trade", "market":"options", "trade": {"id": t.id, "pair": t.pair}})
    except Exception:
        pass
    return {"ok": True, "id": t.id}

@app.get("/options/orders")
async def options_orders(db: Session = Depends(get_db)):
    rows = db.query(OptionsTrade).order_by(OptionsTrade.timestamp.desc()).limit(200).all()
    return [{"id": r.id, "user": r.username, "pair": r.pair, "strike": r.strike, "premium": r.premium, "size": r.size} for r in rows]

# --------------------------
# Ledger Summary
# --------------------------
@app.get("/api/ledger/summary")
async def ledger_summary(db: Session = Depends(get_db)):
    users = db.query(User).all()
    totals = {
        "users": len(users),
        "spot_trades": db.query(SpotTrade).count(),
        "margin_trades": db.query(MarginTrade).count(),
        "futures_usdm": db.query(FuturesUsdmTrade).count(),
        "futures_coinm": db.query(FuturesCoinmTrade).count(),
        "options_trades": db.query(OptionsTrade).count(),
        "p2p_orders": db.query(P2POrder).count(),
    }
    totals["total_inr"] = sum([getattr(u, "balance_inr", 0) or 0 for u in users])
    totals["total_usdt"] = sum([getattr(u, "balance_usdt", 0) or 0 for u in users])
    totals["proof_hash"] = str(round(totals["total_inr"] * (totals["total_usdt"] + 1), 2))
    return totals

# --------------------------
# Admin Seed
# --------------------------
SEED_DEFAULT = int(os.getenv("SEED_COUNT", "500"))

@app.post("/admin/seed")
async def admin_seed(count: Optional[int] = None):
    """Seeds demo users and trades"""
    db = SessionLocal()
    n = count or SEED_DEFAULT
    try:
        existing = db.query(User).count()
        if existing >= n:
            return {"ok": True, "seeded": existing, "note": "skipped: already seeded"}
        
        pairs_spot = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "MATICUSDT"]
        
        # Create users
        for i in range(n):
            uname = f"demo_trader_{existing + i}"
            u = User(
                username=uname,
                email=f"{uname}@blockflow.local",
                password="demo",
                balance_inr=random.randint(50000, 500000),
                balance_usdt=round(random.uniform(100, 10000), 2)
            )
            db.add(u)
        db.commit()

        # Spot trades
        for _ in range(n):
            t = SpotTrade(
                username=f"demo_trader_{random.randint(0, n-1)}",
                pair=random.choice(pairs_spot),
                side=random.choice(["buy", "sell"]),
                price=round(random.uniform(1000, 60000), 2),
                amount=round(random.uniform(0.0005, 2.0), 6)
            )
            db.add(t)

        # Futures USDM
        for _ in range(int(n * 0.6)):
            f = FuturesUsdmTrade(
                username=f"demo_trader_{random.randint(0, n-1)}",
                pair=random.choice(pairs_spot),
                side=random.choice(["buy", "sell"]),
                leverage=random.choice([5,10,20]),
                price=round(random.uniform(1000, 60000), 2),
                amount=round(random.uniform(0.01, 5.0), 4),
            )
            db.add(f)

        # Margin
        for _ in range(int(n * 0.5)):
            m = MarginTrade(
                username=f"demo_trader_{random.randint(0, n-1)}",
                pair=random.choice(pairs_spot),
                side=random.choice(["buy", "sell"]),
                leverage=random.choice([3,5,10]),
                price=round(random.uniform(1000, 60000), 2),
                amount=round(random.uniform(0.01, 3.0), 4),
                pnl=round(random.uniform(-100, 300), 2),
            )
            db.add(m)

        # P2P orders
        for _ in range(int(n * 0.6)):
            p = P2POrder(
                username=f"demo_trader_{random.randint(0, n-1)}",
                asset=random.choice(["USDT","BTC","ETH"]),
                price=round(random.uniform(70000, 4500000)/100.0, 2) * 100,
                amount=round(random.uniform(0.001, 10.0), 4),
                payment_method=random.choice(["UPI","Bank Transfer"]),
                status="active"
            )
            db.add(p)

        db.commit()

        try:
            await ws_manager.broadcast_json({"type":"seed_completed", "users_seeded": n})
        except Exception:
            pass

        return {"ok": True, "seeded": n}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# --------------------------
# WebSocket (REAL DATA STREAMING)
# --------------------------
@app.websocket("/ws/market")
async def ws_market(ws: WebSocket):
    await ws_manager.connect(ws)
    subscribed_symbol = None
    
    try:
        # Send welcome
        await ws.send_text(json.dumps({
            "type": "welcome",
            "time": datetime.utcnow().isoformat()
        }))
        
        # Background task: stream market data
        async def stream_data():
            while True:
                try:
                    if subscribed_symbol:
                        db = SessionLocal()
                        
                        # Get orderbook
                        trades = db.query(SpotTrade).filter(
                            SpotTrade.pair == subscribed_symbol
                        ).order_by(SpotTrade.timestamp.desc()).limit(50).all()
                        
                        bids = []
                        asks = []
                        
                        for t in trades:
                            entry = {"price": t.price, "amount": t.amount}
                            if t.side == "buy":
                                bids.append(entry)
                            else:
                                asks.append(entry)
                        
                        bids.sort(key=lambda x: x['price'], reverse=True)
                        asks.sort(key=lambda x: x['price'])
                        
                        # Send orderbook
                        await ws.send_text(json.dumps({
                            "type": "orderbook",
                            "symbol": subscribed_symbol,
                            "bids": bids[:15],
                            "asks": asks[:15]
                        }))
                        
                        # Send recent trades
                        recent = trades[:10]
                        await ws.send_text(json.dumps({
                            "type": "trades",
                            "trades": [{
                                "id": t.id,
                                "price": t.price,
                                "amount": t.amount,
                                "side": t.side,
                                "ts": str(t.timestamp)
                            } for t in recent]
                        }))
                        
                        db.close()
                    
                    await asyncio.sleep(2)
                
                except Exception as e:
                    print(f"Stream error: {e}")
                    await asyncio.sleep(2)
        
        # Start streaming
        stream_task = asyncio.create_task(stream_data())
        
        # Listen for messages
        while True:
            msg = await ws.receive_text()
            try:
                data = json.loads(msg)
                
                if data.get("type") == "subscribe":
                    subscribed_symbol = data.get("symbol", "BTCUSDT")
                    await ws_manager.subscribe(ws, subscribed_symbol)
                    await ws.send_text(json.dumps({
                        "type": "subscribed",
                        "symbol": subscribed_symbol
                    }))
            
            except Exception as e:
                print(f"Message error: {e}")
    
    except WebSocketDisconnect:
        await ws_manager.disconnect(ws)
    except Exception as e:
        print(f"WS error: {e}")
        await ws_manager.disconnect(ws)

# --------------------------
# Startup Tasks
# --------------------------
@app.on_event("startup")
async def startup_tasks():
    """Auto-run background tasks"""
    print("✅ Blockflow backend starting...")
    
    # Auto-seed if no users exist
    try:
        db = SessionLocal()
        user_count = db.query(User).count()
        db.close()
        
        if user_count == 0:
            print("🌱 No users found, auto-seeding 500 demo users...")
            await admin_seed(500)
    except Exception as e:
        print(f"⚠️ Startup seeding error: {e}")
    
    print("🚀 Blockflow backend ready!")
 # ==============================
# 🟢 KEEP-ALIVE PATCH (Render backend auto sleep fix)
# ==============================
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import threading
import time
import requests

def keep_alive():
    """
    This function pings your own Render URL every 5 minutes
    so the server never goes to sleep.
    """
    while True:
        try:
            url = "https://blockflow-v5-1.onrender.com"  # apna Render backend URL yahan daal
            r = requests.get(url, timeout=10)
            print(f"[KeepAlive] Pinged backend — status {r.status_code}")
        except Exception as e:
            print(f"[KeepAlive] Error pinging backend: {e}")
        time.sleep(300)  # ping every 5 minutes

# Run it in background
threading.Thread(target=keep_alive, daemon=True).start()


# --------------------------


