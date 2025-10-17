"""
FINAL main.py — Ready-to-paste
Sovereign demo backend for Blockflow (FastAPI + SQLite).
- Requires your app.models to exist (User, P2POrder, SpotTrade, MarginTrade, FuturesUsdmTrade, FuturesCoinmTrade, OptionsTrade)
- Creates tables if missing
- Exposes trade endpoints + ws broadcast + ledger summary + admin seeder
"""

import asyncio
import json
import random
import logging
from datetime import datetime
from typing import List, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Change this import if your models live elsewhere (e.g. models.py)
import app.models as models  # expects: app/models.py with Base and model classes

# ---------- Database ----------
DB_PATH = "sqlite:///./blockflow_v5.db"
engine = create_engine(DB_PATH, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ensure tables exist on startup
models.Base.metadata.create_all(bind=engine)

# ---------- App ----------
app = FastAPI(title="Blockflow Exchange (Demo)", version="v1-demo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("uvicorn.error")

# ---------- Simple dependency ----------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------- WebSocket manager ----------
class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        logger.debug("WS: client connected")

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)
            logger.debug("WS: client disconnected")

    async def broadcast(self, message: Dict[str, Any]):
        living = []
        payload = json.dumps(message)
        for ws in list(self.active):
            try:
                await ws.send_text(payload)
                living.append(ws)
            except Exception:
                # ignore dead connection
                pass
        self.active = living

manager = ConnectionManager()

# ---------- Pydantic request models ----------
class TradeRequest(BaseModel):
    username: str
    pair: str
    side: str  # buy / sell
    price: float
    amount: float
    leverage: float = 1.0  # optional for derivatives

class P2POrderRequest(BaseModel):
    username: str
    asset: str
    price: float
    amount: float
    payment_method: str

# ---------- Health & root ----------
@app.get("/")
async def root():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}

@app.get("/health")
async def health():
    return {"status": "ok"}

# ---------- WebSocket endpoint for market feed ----------
@app.websocket("/ws/market")
async def ws_market(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            # server doesn't expect client messages — but keep connection alive
            data = await ws.receive_text()
            # optionally, client can request "ping" or "subscribe"
            if data:
                try:
                    msg = json.loads(data)
                except Exception:
                    msg = {"raw": data}
                # echo small acks if needed
                await ws.send_text(json.dumps({"ack": msg}))
    except WebSocketDisconnect:
        manager.disconnect(ws)

# ---------- P2P endpoints ----------
@app.get("/p2p/orders")
def list_p2p(db: Session = Depends(get_db)):
    rows = db.query(models.P2POrder).order_by(models.P2POrder.created_at.desc()).all()
    return [dict(id=r.id, username=r.username, asset=r.asset, price=r.price, amount=r.amount, payment_method=r.payment_method, status=r.status, created_at=str(r.created_at)) for r in rows]

@app.post("/p2p/create")
async def create_p2p(order: P2POrderRequest, db: Session = Depends(get_db)):
    o = models.P2POrder(
        username=order.username,
        asset=order.asset,
        price=order.price,
        amount=order.amount,
        payment_method=order.payment_method,
        status="open"
    )
    db.add(o); db.commit(); db.refresh(o)
    await manager.broadcast({"type": "p2p_new", "order": {"id": o.id, "username": o.username, "asset": o.asset, "price": o.price, "amount": o.amount}})
    return {"ok": True, "id": o.id}

@app.post("/p2p/settle/{order_id}")
async def settle_p2p(order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.P2POrder).filter(models.P2POrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="order not found")
    order.status = "settled"
    db.commit()
    # demo TDS calc
    tds = round(order.price * order.amount * 0.01, 2)
    await manager.broadcast({"type": "p2p_settled", "order_id": order_id, "tds": tds})
    return {"ok": True, "tds": tds}

# ---------- Spot / Margin / Futures / Options endpoints ----------
# Spot
@app.post("/spot/trade")
async def spot_trade(req: TradeRequest, db: Session = Depends(get_db)):
    t = models.SpotTrade(username=req.username, pair=req.pair, side=req.side, price=req.price, amount=req.amount)
    db.add(t); db.commit(); db.refresh(t)
    await manager.broadcast({"type": "trade_executed", "market": "spot", "trade": {"id": t.id, "username": t.username, "pair": t.pair, "side": t.side, "price": t.price, "amount": t.amount}})
    return {"ok": True, "trade_id": t.id}

# Margin
@app.post("/margin/trade")
async def margin_trade(req: TradeRequest, db: Session = Depends(get_db)):
    t = models.MarginTrade(username=req.username, pair=req.pair, side=req.side, leverage=req.leverage, price=req.price, amount=req.amount, pnl=0.0)
    # simple PnL demo calc (not real)
    t.pnl = round((req.amount * req.price) / max(1.0, req.leverage) * (0.02 if req.side == "sell" else -0.02), 4)
    db.add(t); db.commit(); db.refresh(t)
    await manager.broadcast({"type": "trade_executed", "market": "margin", "trade": {"id": t.id, "username": t.username, "pair": t.pair, "side": t.side, "price": t.price, "amount": t.amount, "leverage": t.leverage}})
    return {"ok": True, "trade_id": t.id, "pnl": t.pnl}

# Futures USDM
@app.post("/futures/usdm/trade")
async def futures_usdm_trade(req: TradeRequest, db: Session = Depends(get_db)):
    t = models.FuturesUsdmTrade(username=req.username, pair=req.pair, side=req.side, leverage=req.leverage, price=req.price, amount=req.amount, pnl=0.0)
    db.add(t); db.commit(); db.refresh(t)
    await manager.broadcast({"type": "trade_executed", "market": "futures_usdm", "trade": {"id": t.id, "username": t.username, "pair": t.pair}})
    return {"ok": True, "trade_id": t.id}

# Futures COINM
@app.post("/futures/coinm/trade")
async def futures_coinm_trade(req: TradeRequest, db: Session = Depends(get_db)):
    t = models.FuturesCoinmTrade(username=req.username, pair=req.pair, side=req.side, leverage=req.leverage, price=req.price, amount=req.amount, pnl=0.0)
    db.add(t); db.commit(); db.refresh(t)
    await manager.broadcast({"type": "trade_executed", "market": "futures_coinm", "trade": {"id": t.id, "username": t.username, "pair": t.pair}})
    return {"ok": True, "trade_id": t.id}

# Options
class OptionsReq(BaseModel):
    username: str
    pair: str
    side: str
    strike: float
    option_type: str
    premium: float
    size: float

@app.post("/options/trade")
async def options_trade(req: OptionsReq, db: Session = Depends(get_db)):
    t = models.OptionsTrade(username=req.username, pair=req.pair, side=req.side, strike=req.strike, option_type=req.option_type, premium=req.premium, size=req.size)
    db.add(t); db.commit(); db.refresh(t)
    await manager.broadcast({"type": "trade_executed", "market": "options", "trade": {"id": t.id, "username": t.username, "pair": t.pair}})
    return {"ok": True, "trade_id": t.id}

# ---------- Order list endpoints for UI consumption ----------
@app.get("/spot/orders")
def list_spot_orders(db: Session = Depends(get_db)):
    rows = db.query(models.SpotTrade).order_by(models.SpotTrade.timestamp.desc()).limit(200).all()
    return [dict(id=r.id, username=r.username, pair=r.pair, side=r.side, price=r.price, amount=r.amount, ts=str(r.timestamp)) for r in rows]

@app.get("/margin/orders")
def list_margin_orders(db: Session = Depends(get_db)):
    rows = db.query(models.MarginTrade).order_by(models.MarginTrade.timestamp.desc()).limit(200).all()
    return [dict(id=r.id, username=r.username, pair=r.pair, side=r.side, price=r.price, amount=r.amount, leverage=r.leverage, ts=str(r.timestamp)) for r in rows]

@app.get("/futures/usdm/orders")
def list_futures_usdm(db: Session = Depends(get_db)):
    rows = db.query(models.FuturesUsdmTrade).order_by(models.FuturesUsdmTrade.timestamp.desc()).limit(200).all()
    return [dict(id=r.id, username=r.username, pair=r.pair, side=r.side, price=r.price, amount=r.amount, leverage=r.leverage, ts=str(r.timestamp)) for r in rows]

@app.get("/futures/coinm/orders")
def list_futures_coinm(db: Session = Depends(get_db)):
    rows = db.query(models.FuturesCoinmTrade).order_by(models.FuturesCoinmTrade.timestamp.desc()).limit(200).all()
    return [dict(id=r.id, username=r.username, pair=r.pair, side=r.side, price=r.price, amount=r.amount, leverage=r.leverage, ts=str(r.timestamp)) for r in rows]

@app.get("/options/orders")
def list_options(db: Session = Depends(get_db)):
    rows = db.query(models.OptionsTrade).order_by(models.OptionsTrade.timestamp.desc()).limit(200).all()
    return [dict(id=r.id, username=r.username, pair=r.pair, side=r.side, strike=r.strike, premium=r.premium, size=r.size, ts=str(r.timestamp)) for r in rows]

# ---------- Ledger / Proof-of-Reserves summary ----------
@app.get("/api/ledger/summary")
def ledger_summary(db: Session = Depends(get_db)):
    totals = {}
    totals['spot_trades'] = db.query(models.SpotTrade).count()
    totals['margin_trades'] = db.query(models.MarginTrade).count()
    totals['futures_usdm'] = db.query(models.FuturesUsdmTrade).count()
    totals['futures_coinm'] = db.query(models.FuturesCoinmTrade).count()
    totals['options_trades'] = db.query(models.OptionsTrade).count()
    # balances (aggregate)
    users = db.query(models.User).all()
    totals['users'] = len(users)
    totals['total_inr'] = sum([u.balance_inr or 0 for u in users])
    totals['total_usdt'] = sum([u.balance_usdt or 0 for u in users])
    # simple proof/hash (demo)
    totals['proof_hash'] = str(round(totals['total_inr'] * (totals['total_usdt'] + 1), 5))
    return totals

# ---------- Admin seeder (POST) - call once ----------
@app.post("/admin/seed")
def admin_seed(db: Session = Depends(get_db)):
    # create demo users if not exist
    existing = db.query(models.User).count()
    if existing >= 500:
        return {"ok": True, "message": "seed already present", "users": existing}
    pairs = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
    for i in range(500):
        u = models.User(username=f"demo_trader_{i}", email=f"demo{i}@blockflow.com", password="demo123", balance_inr=random.randint(50000, 500000), balance_usdt=round(random.uniform(1000, 10000), 2))
        db.add(u)
    db.commit()
    # seed 500 spot trades + 200 random futures + 100 options
    for _ in range(500):
        t = models.SpotTrade(username=f"demo_trader_{random.randint(0,499)}", pair=random.choice(pairs), side=random.choice(["buy","sell"]), price=round(random.uniform(1000,60000),2), amount=round(random.uniform(0.01,1.0),4))
        db.add(t)
    for _ in range(200):
        f = models.FuturesUsdmTrade(username=f"demo_trader_{random.randint(0,499)}", pair=random.choice(pairs), side=random.choice(["buy","sell"]), leverage=random.choice([5,10,20]), price=round(random.uniform(1000,60000),2), amount=round(random.uniform(0.01,2.0),4))
        db.add(f)
    for _ in range(100):
        op = models.OptionsTrade(username=f"demo_trader_{random.randint(0,499)}", pair=random.choice(pairs), side=random.choice(["buy","sell"]), strike=round(random.uniform(1000,60000),2), option_type=random.choice(["call","put"]), premium=round(random.uniform(1,5000),2), size=round(random.uniform(0.1,10),2))
        db.add(op)
    db.commit()
    # broadcast a few demo events
    asyncio.create_task(manager.broadcast({"type":"seed_completed", "message":"demo seed finished"}))
    return {"ok": True, "seeded": True}

# ---------- Simple register/login (demo-only; for integration tests) ----------
class RegisterReq(BaseModel):
    username: str
    email: str
    password: str

@app.post("/register")
def register(r: RegisterReq, db: Session = Depends(get_db)):
    exists = db.query(models.User).filter(models.User.username==r.username).first()
    if exists:
        raise HTTPException(status_code=400, detail="username exists")
    u = models.User(username=r.username, email=r.email, password=r.password, balance_inr=100000, balance_usdt=1000)
    db.add(u); db.commit(); db.refresh(u)
    return {"ok": True, "id": u.id}

@app.post("/login")
def login(r: RegisterReq, db: Session = Depends(get_db)):
    u = db.query(models.User).filter(models.User.username==r.username, models.User.password==r.password).first()
    if not u:
        raise HTTPException(status_code=401, detail="invalid credentials")
    # demo token (not JWT) — replace with real JWT as needed
    token = f"demo-token-{u.id}"
    return {"ok": True, "token": token, "user": {"id": u.id, "username": u.username}}

# ---------- Small helper: broadcast recent trade summary periodically (demo flavor) ----------
async def periodic_demo_broadcast():
    while True:
        try:
            db = SessionLocal()
            latest = db.query(models.SpotTrade).order_by(models.SpotTrade.timestamp.desc()).limit(5).all()
            summary = [{"id": t.id, "pair": t.pair, "price": t.price, "amount": t.amount} for t in latest]
            await manager.broadcast({"type": "market_snapshot", "spot_recent": summary, "time": datetime.utcnow().isoformat()})
        except Exception as e:
            logger.exception("periodic demo broadcast error")
        finally:
            db.close()
        await asyncio.sleep(5)

@app.on_event("startup")
async def startup_tasks():
    # start background broadcast
    asyncio.create_task(periodic_demo_broadcast())
    logger.info("Blockflow demo backend started")

# ---------- Run with: uvicorn main:app --reload ----------
# End of file

    logger.info("Launching uvicorn for main:app")
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)

