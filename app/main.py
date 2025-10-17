# app/main.py
"""
Final unified Blockflow backend (Render-ready).
- Auto-detects DB path (DATABASE_URL env or common fallbacks)
- Attempts `import app.models` then `import models`
- Provides P2P, Spot, Margin, Futures (USDM & COINM), Options endpoints
- WebSocket /ws/market broadcast
- /admin/seed to create demo liquidity (configurable via env SEED_COUNT)
- /api/ledger/summary for ledger/proof-of-reserves
- Safe startup for Render (no uvicorn.run())
"""

import os
import json
import random
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# ---- dynamic models import (works whether models live at app.models or models) ----
try:
    import app.models as models  # preferred
except Exception:
    try:
        import models
    except Exception as e:
        raise ImportError("Could not import models. Ensure app/models.py or models.py exists.") from e

# ---- DB path detection ----
# Priority:
# 1) env DATABASE_URL
# 2) sqlite in project root ./blockflow_v5.db
# 3) sqlite in ./app/blockflow_v5.db
# 4) sqlite at ../blockflow_v5.db
def _detect_db_url() -> str:
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
        # check file existence when using sqlite path (strip prefix)
        if c.startswith("sqlite:///"):
            path = c.replace("sqlite:///", "")
            if os.path.exists(path):
                return c
    # fallback to first candidate
    return candidates[0]

DATABASE_URL = _detect_db_url()

# ---- SQLAlchemy engine & session ----
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# create tables if missing (safe to call on startup)
try:
    models.Base.metadata.create_all(bind=engine)
except Exception as e:
    # provide explicit error context if models mismatch
    print("ERROR creating tables:", e)

# ---- FastAPI app ----
app = FastAPI(title="Blockflow Exchange (Unified Demo)", version="v5")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ---- dependency ----
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---- websocket manager ----
class WSManager:
    def __init__(self):
        self.clients: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.clients.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.clients:
            self.clients.remove(ws)

    async def broadcast(self, payload: Dict[str, Any]):
        text = json.dumps(payload, default=str)
        living = []
        for ws in list(self.clients):
            try:
                await ws.send_text(text)
                living.append(ws)
            except Exception:
                # skip dead
                pass
        self.clients = living

ws_manager = WSManager()

# ---- Pydantic request schemas ----
class P2PCreateReq(BaseModel):
    username: str
    asset: str
    price: float
    amount: float
    payment_method: str

class TradeReq(BaseModel):
    username: str
    pair: str
    side: str  # buy/sell
    price: float
    amount: float
    leverage: Optional[float] = 1.0

class OptionReq(BaseModel):
    username: str
    pair: str
    side: str
    strike: float
    option_type: str
    premium: float
    size: float

# ---- Health / root ----
@app.get("/")
async def root():
    return {"ok": True, "time": datetime.utcnow().isoformat(), "db": DATABASE_URL}

@app.get("/health")
async def health():
    return {"ok": True, "services": ["p2p", "spot", "margin", "futures_usdm", "futures_coinm", "options"], "db": DATABASE_URL}

# ---------------- P2P ----------------
@app.get("/p2p/orders")
def p2p_list(db: Session = Depends(get_db)):
    rows = db.query(models.P2POrder).order_by(models.P2POrder.created_at.desc()).all()
    return [dict(id=r.id, username=r.username, asset=r.asset, price=r.price, amount=r.amount, payment_method=r.payment_method, status=r.status, created_at=str(r.created_at)) for r in rows]

@app.post("/p2p/create")
async def p2p_create(req: P2PCreateReq, db: Session = Depends(get_db)):
    o = models.P2POrder(username=req.username, asset=req.asset, price=req.price, amount=req.amount, payment_method=req.payment_method, status="open")
    db.add(o); db.commit(); db.refresh(o)
    await ws_manager.broadcast({"type":"p2p_new", "order": {"id": o.id, "username": o.username, "asset": o.asset, "price": o.price, "amount": o.amount}})
    return {"ok": True, "id": o.id}

@app.post("/p2p/settle/{order_id}")
async def p2p_settle(order_id: int, db: Session = Depends(get_db)):
    o = db.query(models.P2POrder).filter(models.P2POrder.id == order_id).first()
    if not o:
        raise HTTPException(404, "order not found")
    o.status = "settled"
    db.commit()
    tds = round(o.price * o.amount * 0.01, 2)
    await ws_manager.broadcast({"type":"p2p_settle", "order_id": order_id, "tds": tds})
    return {"ok": True, "tds": tds}

# ---------------- Spot ----------------
@app.post("/spot/trade")
async def spot_trade(req: TradeReq, db: Session = Depends(get_db)):
    t = models.SpotTrade(username=req.username, pair=req.pair, side=req.side, price=req.price, amount=req.amount)
    db.add(t); db.commit(); db.refresh(t)
    await ws_manager.broadcast({"type":"trade", "market":"spot", "trade": {"id": t.id, "pair": t.pair, "price": t.price, "amount": t.amount, "side": t.side}})
    return {"ok": True, "trade_id": t.id}

@app.get("/spot/orders")
def spot_orders(db: Session = Depends(get_db)):
    rows = db.query(models.SpotTrade).order_by(models.SpotTrade.timestamp.desc()).limit(500).all()
    return [dict(id=r.id, username=r.username, pair=r.pair, side=r.side, price=r.price, amount=r.amount, ts=str(r.timestamp)) for r in rows]

# ---------------- Margin ----------------
@app.post("/margin/trade")
async def margin_trade(req: TradeReq, db: Session = Depends(get_db)):
    t = models.MarginTrade(username=req.username, pair=req.pair, side=req.side, leverage=req.leverage or 10.0, price=req.price, amount=req.amount, pnl=0.0)
    # demo pnl
    t.pnl = round((t.amount * t.price) / max(1.0, t.leverage) * (0.02 if t.side == "sell" else -0.02), 4)
    db.add(t); db.commit(); db.refresh(t)
    await ws_manager.broadcast({"type":"trade", "market":"margin", "trade": {"id": t.id, "pair": t.pair, "price": t.price}})
    return {"ok": True, "trade_id": t.id, "pnl": t.pnl}

@app.get("/margin/orders")
def margin_orders(db: Session = Depends(get_db)):
    rows = db.query(models.MarginTrade).order_by(models.MarginTrade.timestamp.desc()).limit(500).all()
    return [dict(id=r.id, username=r.username, pair=r.pair, side=r.side, price=r.price, leverage=r.leverage, amount=r.amount, pnl=r.pnl, ts=str(r.timestamp)) for r in rows]

# ---------------- Futures USDM ----------------
@app.post("/futures/usdm/trade")
async def futures_usdm_trade(req: TradeReq, db: Session = Depends(get_db)):
    # expects models.FuturesUsdmTrade
    t = models.FuturesUsdmTrade(username=req.username, pair=req.pair, side=req.side, leverage=req.leverage or 20.0, price=req.price, amount=req.amount, pnl=0.0)
    db.add(t); db.commit(); db.refresh(t)
    await ws_manager.broadcast({"type":"trade", "market":"futures_usdm", "trade":{"id": t.id, "pair": t.pair, "price": t.price}})
    return {"ok": True, "trade_id": t.id}

@app.get("/futures/usdm/orders")
def futures_usdm_orders(db: Session = Depends(get_db)):
    rows = db.query(models.FuturesUsdmTrade).order_by(models.FuturesUsdmTrade.timestamp.desc()).limit(500).all()
    return [dict(id=r.id, username=r.username, pair=r.pair, side=r.side, price=r.price, leverage=r.leverage, amount=r.amount, pnl=r.pnl, ts=str(r.timestamp)) for r in rows]

# ---------------- Futures COINM ----------------
@app.post("/futures/coinm/trade")
async def futures_coinm_trade(req: TradeReq, db: Session = Depends(get_db)):
    t = models.FuturesCoinmTrade(username=req.username, pair=req.pair, side=req.side, leverage=req.leverage or 20.0, price=req.price, amount=req.amount, pnl=0.0)
    db.add(t); db.commit(); db.refresh(t)
    await ws_manager.broadcast({"type":"trade", "market":"futures_coinm", "trade":{"id": t.id, "pair": t.pair, "price": t.price}})
    return {"ok": True, "trade_id": t.id}

@app.get("/futures/coinm/orders")
def futures_coinm_orders(db: Session = Depends(get_db)):
    rows = db.query(models.FuturesCoinmTrade).order_by(models.FuturesCoinmTrade.timestamp.desc()).limit(500).all()
    return [dict(id=r.id, username=r.username, pair=r.pair, side=r.side, price=r.price, leverage=r.leverage, amount=r.amount, pnl=r.pnl, ts=str(r.timestamp)) for r in rows]

# ---------------- Options ----------------
@app.post("/options/trade")
async def options_trade(req: OptionReq, db: Session = Depends(get_db)):
    t = models.OptionsTrade(username=req.username, pair=req.pair, side=req.side, strike=req.strike, option_type=req.option_type, premium=req.premium, size=req.size)
    db.add(t); db.commit(); db.refresh(t)
    await ws_manager.broadcast({"type":"trade", "market":"options", "trade":{"id": t.id, "pair": t.pair}})
    return {"ok": True, "trade_id": t.id}

@app.get("/options/orders")
def options_orders(db: Session = Depends(get_db)):
    rows = db.query(models.OptionsTrade).order_by(models.OptionsTrade.timestamp.desc()).limit(500).all()
    return [dict(id=r.id, username=r.username, pair=r.pair, side=r.side, strike=r.strike, premium=r.premium, size=r.size, ts=str(r.timestamp)) for r in rows]

# ---------------- Ledger / PoR ----------------
@app.get("/api/ledger/summary")
def ledger_summary(db: Session = Depends(get_db)):
    totals = {}
    totals['spot_trades'] = db.query(models.SpotTrade).count()
    totals['margin_trades'] = db.query(models.MarginTrade).count()
    totals['futures_usdm'] = db.query(models.FuturesUsdmTrade).count()
    totals['futures_coinm'] = db.query(models.FuturesCoinmTrade).count()
    totals['options_trades'] = db.query(models.OptionsTrade).count()
    users = db.query(models.User).all()
    totals['users'] = len(users)
    totals['total_inr'] = sum([u.balance_inr or 0 for u in users])
    totals['total_usdt'] = sum([u.balance_usdt or 0 for u in users])
    totals['proof_hash'] = str(round(totals['total_inr'] * (totals['total_usdt'] + 1), 5))
    return totals

# ---------------- Admin seed (configurable count) ----------------
@app.post("/admin/seed")
def admin_seed(db: Session = Depends(get_db)):
    # seed count can be tweaked with env: SEED_COUNT (default 500)
    SEED_COUNT = int(os.getenv("SEED_COUNT", "500"))
    # create users (if not exist)
    existing = db.query(models.User).count()
    if existing >= SEED_COUNT:
        return {"ok": True, "message": "already seeded", "users": existing}

    pairs = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
    # create users
    for i in range(SEED_COUNT):
        u = models.User(username=f"demo_trader_{i}", email=f"demo{i}@blockflow.com", password="demo123", balance_inr=random.randint(50000, 500000), balance_usdt=round(random.uniform(1000, 10000), 2))
        db.add(u)
    db.commit()

    # seed spot trades
    for _ in range(int(SEED_COUNT * 1.0)):  # ~1x spot
        t = models.SpotTrade(username=f"demo_trader_{random.randint(0, SEED_COUNT-1)}", pair=random.choice(pairs), side=random.choice(["buy","sell"]), price=round(random.uniform(1000, 60000), 2), amount=round(random.uniform(0.001, 1.0), 6))
        db.add(t)

    # seed futures usdm
    for _ in range(int(SEED_COUNT * 0.5)):
        f = models.FuturesUsdmTrade(username=f"demo_trader_{random.randint(0, SEED_COUNT-1)}", pair=random.choice(pairs), side=random.choice(["buy","sell"]), leverage=random.choice([5,10,20]), price=round(random.uniform(1000,60000),2), amount=round(random.uniform(0.01,2.0),4))
        db.add(f)

    # seed futures coinm
    for _ in range(int(SEED_COUNT * 0.3)):
        f = models.FuturesCoinmTrade(username=f"demo_trader_{random.randint(0, SEED_COUNT-1)}", pair=random.choice(pairs), side=random.choice(["buy","sell"]), leverage=random.choice([2,5,10]), price=round(random.uniform(1000,60000),2), amount=round(random.uniform(0.01,5.0),4))
        db.add(f)

    # seed options
    for _ in range(int(SEED_COUNT * 0.2)):
        op = models.OptionsTrade(username=f"demo_trader_{random.randint(0, SEED_COUNT-1)}", pair=random.choice(pairs), side=random.choice(["buy","sell"]), strike=round(random.uniform(1000,60000),2), option_type=random.choice(["call","put"]), premium=round(random.uniform(1,5000),2), size=round(random.uniform(0.1,10),2))
        db.add(op)

    db.commit()
    # broadcast a seed completed message to websocket clients
    asyncio.create_task(ws_manager.broadcast({"type":"seed_completed", "users": SEED_COUNT}))
    return {"ok": True, "seeded_users": SEED_COUNT}

# ---------------- WebSocket endpoint ----------------
@app.websocket("/ws/market")
async def ws_market(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            # keep connection open, accept pings/pongs
            data = await ws.receive_text()
            # optional client messages are logged and acknowledged
            try:
                payload = json.loads(data)
            except Exception:
                payload = {"raw": data}
            # echo ack
            await ws.send_text(json.dumps({"ack": payload}))
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)

# ---------------- periodic broadcaster (market snapshot) ----------------
async def periodic_broadcast():
    while True:
        await asyncio.sleep(5)
        try:
            db = SessionLocal()
            latest_spot = db.query(models.SpotTrade).order_by(models.SpotTrade.timestamp.desc()).limit(5).all()
            snapshot = [{"id": t.id, "pair": t.pair, "price": t.price, "amount": t.amount} for t in latest_spot]
            await ws_manager.broadcast({"type":"market_snapshot", "spot_recent": snapshot, "time": datetime.utcnow().isoformat()})
        except Exception:
            pass
        finally:
            try:
                db.close()
            except Exception:
                pass

@app.on_event("startup")
async def startup_event():
    # start periodic broadcaster but do NOT start uvicorn.run here (Render runs server)
    asyncio.create_task(periodic_broadcast())

# ---------------- end file ----------------


