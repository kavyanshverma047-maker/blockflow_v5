# app/main.py
"""
Blockflow Exchange — Final investor-grade backend (Render-ready)
Features:
 - P2P orders (create, list, settle)
 - Spot / Margin / Futures (USDM & COINM) / Options endpoints (place & list)
 - WebSocket real-time feed at /ws/market
 - /admin/seed -> seeds 500 demo users + trades (async, safe)
 - /api/ledger/summary -> quick ledger totals & PoR-like hash
 - Periodic market simulator to keep UI alive
 - DB autodetect (DATABASE_URL env or sqlite fallback)
 - Uses existing app.models (User, P2POrder, SpotTrade, MarginTrade,
   FuturesUsdmTrade, FuturesCoinmTrade, OptionsTrade, Base)
"""

import os
import json
import random
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.price_feed import fetch_prices
from app.demo_trader import simulate_trades

app = FastAPI(title="Blockflow Exchange (Unified Demo)")

@app.on_event("startup")
async def start_background_services():
    asyncio.create_task(fetch_prices())
    asyncio.create_task(simulate_trades())


# Try import models from app.models (preferred) else models
try:
    import app.models as models
except Exception:
    import models

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
app = FastAPI(title="Blockflow Exchange (Investor Demo)", version="5.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --------------------------
# WebSocket manager
# --------------------------
class WebSocketManager:
    def __init__(self):
        self.connections: List[WebSocket] = []
        self.lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self.lock:
            self.connections.append(ws)

    async def disconnect(self, ws: WebSocket):
        async with self.lock:
            if ws in self.connections:
                self.connections.remove(ws)

    async def broadcast_json(self, payload: Dict[str, Any]):
        text = json.dumps(payload, default=str)
        # copy list to avoid mutation during iteration
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
    price: float
    amount: float

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
# root / health
# --------------------------
@app.get("/")
async def root():
    return {"ok": True, "app": "blockflow-exchange", "time": datetime.now(timezone.utc).isoformat()}

@app.get("/health")
async def health():
    return {"ok": True, "db": DATABASE_URL}

# --------------------------
# P2P endpoints
# --------------------------
@app.get("/p2p/orders")
async def p2p_list(db: Session = Depends(get_db)):
    rows = db.query(models.P2POrder).order_by(models.P2POrder.created_at.desc()).limit(500).all()
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
    o = models.P2POrder(
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
    # broadcast to WS clients (best-effort)
    try:
        await ws_manager.broadcast_json({"type":"p2p_new", "order": {"id": o.id, "username": o.username, "asset": o.asset, "price": o.price, "amount": o.amount}})
    except Exception:
        pass
    return {"ok": True, "id": o.id}

@app.post("/p2p/settle/{order_id}")
async def p2p_settle(order_id: int, db: Session = Depends(get_db)):
    o = db.query(models.P2POrder).filter(models.P2POrder.id == order_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="order not found")
    o.status = "settled"
    db.commit()
    tds = round((o.price or 0) * (o.amount or 0) * 0.01, 2)
    # broadcast settlement
    try:
        await ws_manager.broadcast_json({"type":"p2p_settle", "order_id": o.id, "tds": tds})
    except Exception:
        pass
    return {"ok": True, "tds": tds}

# --------------------------
# Spot endpoints
# --------------------------
@app.post("/spot/trade")
async def spot_trade(req: SpotPlaceSchema, db: Session = Depends(get_db)):
    t = models.SpotTrade(username=req.username, pair=req.pair, side=req.side, price=req.price, amount=req.amount)
    db.add(t); db.commit(); db.refresh(t)
    try:
        await ws_manager.broadcast_json({"type":"trade", "market":"spot", "trade": {"id": t.id, "pair": t.pair, "price": t.price, "amount": t.amount, "side": t.side}})
    except Exception:
        pass
    return {"ok": True, "id": t.id}

@app.get("/spot/orders")
async def spot_orders(db: Session = Depends(get_db)):
    rows = db.query(models.SpotTrade).order_by(models.SpotTrade.timestamp.desc()).limit(200).all()
    return [{"id": r.id, "username": r.username, "pair": r.pair, "price": r.price, "amount": r.amount, "side": r.side, "ts": str(r.timestamp)} for r in rows]

# --------------------------
# Margin endpoints
# --------------------------
@app.post("/margin/trade")
async def margin_trade(req: SpotPlaceSchema, db: Session = Depends(get_db)):
    t = models.MarginTrade(username=req.username, pair=req.pair, side=req.side, leverage= getattr(req, "leverage", 10.0), price=req.price, amount=req.amount, pnl=0.0)
    # small demo pnl calc
    t.pnl = round((t.amount * t.price) * (0.01 if t.side == "sell" else -0.01), 3)
    db.add(t); db.commit(); db.refresh(t)
    try:
        await ws_manager.broadcast_json({"type":"trade", "market":"margin", "trade": {"id": t.id, "pair": t.pair, "price": t.price}})
    except Exception:
        pass
    return {"ok": True, "id": t.id, "pnl": t.pnl}

@app.get("/margin/orders")
async def margin_orders(db: Session = Depends(get_db)):
    rows = db.query(models.MarginTrade).order_by(models.MarginTrade.timestamp.desc()).limit(200).all()
    return [{"id": r.id, "user": r.username, "pair": r.pair, "price": r.price, "amount": r.amount, "pnl": r.pnl} for r in rows]

# --------------------------
# Futures USDM endpoints
# --------------------------
@app.post("/futures/usdm/trade")
async def futures_usdm_trade(req: FuturesPlaceSchema, db: Session = Depends(get_db)):
    t = models.FuturesUsdmTrade(username=req.username, pair=req.pair, side=req.side, leverage=req.leverage or 20.0, price=req.price, amount=req.amount, pnl=0.0)
    db.add(t); db.commit(); db.refresh(t)
    try:
        await ws_manager.broadcast_json({"type":"trade", "market":"futures_usdm", "trade": {"id": t.id, "pair": t.pair, "price": t.price}})
    except Exception:
        pass
    return {"ok": True, "id": t.id}

@app.get("/futures/usdm/orders")
async def futures_usdm_orders(db: Session = Depends(get_db)):
    rows = db.query(models.FuturesUsdmTrade).order_by(models.FuturesUsdmTrade.timestamp.desc()).limit(200).all()
    return [{"id": r.id, "user": r.username, "pair": r.pair, "price": r.price, "amount": r.amount, "leverage": r.leverage} for r in rows]

# --------------------------
# Futures COINM endpoints
# --------------------------
@app.post("/futures/coinm/trade")
async def futures_coinm_trade(req: FuturesPlaceSchema, db: Session = Depends(get_db)):
    t = models.FuturesCoinmTrade(username=req.username, pair=req.pair, side=req.side, leverage=req.leverage or 20.0, price=req.price, amount=req.amount, pnl=0.0)
    db.add(t); db.commit(); db.refresh(t)
    try:
        await ws_manager.broadcast_json({"type":"trade", "market":"futures_coinm", "trade": {"id": t.id, "pair": t.pair, "price": t.price}})
    except Exception:
        pass
    return {"ok": True, "id": t.id}

@app.get("/futures/coinm/orders")
async def futures_coinm_orders(db: Session = Depends(get_db)):
    rows = db.query(models.FuturesCoinmTrade).order_by(models.FuturesCoinmTrade.timestamp.desc()).limit(200).all()
    return [{"id": r.id, "user": r.username, "pair": r.pair, "price": r.price, "amount": r.amount, "leverage": r.leverage} for r in rows]


# --------------------------
# Options endpoints
# --------------------------
@app.post("/options/trade")
async def options_trade(req: OptionsPlaceSchema, db: Session = Depends(get_db)):
    t = models.OptionsTrade(username=req.username, pair=req.pair, side=req.side, strike=req.strike, option_type=req.option_type, premium=req.premium, size=req.size)
    db.add(t); db.commit(); db.refresh(t)
    try:
        await ws_manager.broadcast_json({"type":"trade", "market":"options", "trade": {"id": t.id, "pair": t.pair}})
    except Exception:
        pass
    return {"ok": True, "id": t.id}

@app.get("/options/orders")
async def options_orders(db: Session = Depends(get_db)):
    rows = db.query(models.OptionsTrade).order_by(models.OptionsTrade.timestamp.desc()).limit(200).all()
    return [{"id": r.id, "user": r.username, "pair": r.pair, "strike": r.strike, "premium": r.premium, "size": r.size} for r in rows]
# =========================
# COMMON DICT METHOD FOR ALL MODELS
# =========================
from sqlalchemy.inspection import inspect

def model_as_dict(self):
    return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}

# Attach helper to each model dynamically
for cls in [User, P2POrder, SpotTrade, MarginTrade, FuturesUsdmTrade, FuturesCoinmTrade, OptionsTrade]:
    cls.as_dict = model_as_dict


# --------------------------
# Ledger / Proof-of-Reserves summary
# --------------------------
@app.get("/api/ledger/summary")
async def ledger_summary(db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    totals = {
        "users": len(users),
        "spot_trades": db.query(models.SpotTrade).count(),
        "margin_trades": db.query(models.MarginTrade).count(),
        "futures_usdm": db.query(models.FuturesUsdmTrade).count(),
        "futures_coinm": db.query(models.FuturesCoinmTrade).count(),
        "options_trades": db.query(models.OptionsTrade).count(),
        "p2p_orders": db.query(models.P2POrder).count(),
    }
    totals["total_inr"] = sum([getattr(u, "balance_inr", 0) or 0 for u in users])
    totals["total_usdt"] = sum([getattr(u, "balance_usdt", 0) or 0 for u in users])
    # naive proof "hash"
    totals["proof_hash"] = str(round(totals["total_inr"] * (totals["total_usdt"] + 1), 2))
    return totals

# --------------------------
# ADMIN SEED (async, safe)
# --------------------------
SEED_DEFAULT = int(os.getenv("SEED_COUNT", "500"))

@app.post("/admin/seed")
async def admin_seed(count: Optional[int] = None):
    """
    Seeds demo users and trades.
    - call with no body to seed SEED_DEFAULT users (default 500)
    - returns {"ok": True, "seeded": N}
    """
    db = SessionLocal()
    n = count or SEED_DEFAULT
    try:
        existing = db.query(models.User).count()
        if existing >= n:
            return {"ok": True, "seeded": existing, "note": "skipped: already seeded"}
        pairs_spot = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "MATICUSDT"]
        for i in range(n):
            uname = f"demo_trader_{existing + i}"
            u = models.User(
                username=uname,
                email=f"{uname}@blockflow.local",
                password="demo",
                balance_inr=random.randint(50000, 500000),
                balance_usdt=round(random.uniform(100, 10000), 2)
            )
            db.add(u)
        db.commit()

        # trades
        # spot: ~1x per user
        for _ in range(n):
            t = models.SpotTrade(
                username=f"demo_trader_{random.randint(0, n-1)}",
                pair=random.choice(pairs_spot),
                side=random.choice(["buy", "sell"]),
                price=round(random.uniform(1000, 60000), 2),
                amount=round(random.uniform(0.0005, 2.0), 6)
            )
            db.add(t)

        # futures usdm
        for _ in range(int(n * 0.6)):
            f = models.FuturesUsdmTrade(
                username=f"demo_trader_{random.randint(0, n-1)}",
                pair=random.choice(pairs_spot),
                side=random.choice(["buy", "sell"]),
                leverage=random.choice([5,10,20]),
                price=round(random.uniform(1000, 60000), 2),
                amount=round(random.uniform(0.01, 5.0), 4),
            )
            db.add(f)

        # futures coinm
        for _ in range(int(n * 0.4)):
            f = models.FuturesCoinmTrade(
                username=f"demo_trader_{random.randint(0, n-1)}",
                pair=random.choice(pairs_spot),
                side=random.choice(["buy", "sell"]),
                leverage=random.choice([2,5,10]),
                price=round(random.uniform(1000, 60000), 2),
                amount=round(random.uniform(0.01, 10.0), 4),
            )
            db.add(f)

        # margin
        for _ in range(int(n * 0.5)):
            m = models.MarginTrade(
                username=f"demo_trader_{random.randint(0, n-1)}",
                pair=random.choice(pairs_spot),
                side=random.choice(["buy", "sell"]),
                leverage=random.choice([3,5,10]),
                price=round(random.uniform(1000, 60000), 2),
                amount=round(random.uniform(0.01, 3.0), 4),
                pnl=round(random.uniform(-100, 300), 2),
            )
            db.add(m)

        # options
        for _ in range(int(n * 0.2)):
            op = models.OptionsTrade(
                username=f"demo_trader_{random.randint(0, n-1)}",
                pair=random.choice(pairs_spot),
                side=random.choice(["buy","sell"]),
                strike=round(random.uniform(1000, 60000), 2),
                option_type=random.choice(["call", "put"]),
                premium=round(random.uniform(1, 1500), 2),
                size=round(random.uniform(0.1, 10), 2),
            )
            db.add(op)

        # p2p orders
        for _ in range(int(n * 0.6)):
            p = models.P2POrder(
                username=f"demo_trader_{random.randint(0, n-1)}",
                asset=random.choice(["USDT","BTC","ETH"]),
                price=round(random.uniform(70000, 4500000)/100.0, 2) * 100,  # some INR-like price
                amount=round(random.uniform(0.001, 10.0), 4),
                payment_method=random.choice(["UPI","Bank Transfer"]),
                status="active"
            )
            db.add(p)

        db.commit()

        # broadcast seed completion (best-effort, inside running loop)
        try:
            await ws_manager.broadcast_json({"type":"seed_completed", "users_seeded": n})
        except RuntimeError:
            # if event loop not running for some reason, just skip broadcast
            pass
        except Exception:
            pass

        return {"ok": True, "seeded": n}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# --------------------------
# WebSocket endpoint
# --------------------------
@app.websocket("/ws/market")
async def ws_market(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        # send welcome snapshot
        await ws.send_text(json.dumps({"type":"welcome", "time": datetime.utcnow().isoformat()}))
        while True:
            # keep connection alive; accept pings/echoes
            msg = await ws.receive_text()
            # echo back small ack
            try:
                body = json.loads(msg)
            except Exception:
                body = {"raw": msg}
            # acknowledge
            await ws.send_text(json.dumps({"ack": body}))
    except WebSocketDisconnect:
        await ws_manager.disconnect(ws)
    except Exception:
        # ensure removal on error
        await ws_manager.disconnect(ws)

# --------------------------
# Periodic market snapshot broadcaster (keeps UI alive)
# --------------------------
async def market_snapshot_loop():
    await asyncio.sleep(2)  # small delay for startup
    while True:
        try:
            db = SessionLocal()
            # fetch recent spot trades (last 5)
            recent_spot = db.query(models.SpotTrade).order_by(models.SpotTrade.timestamp.desc()).limit(6).all()
            recent_f_usdm = db.query(models.FuturesUsdmTrade).order_by(models.FuturesUsdmTrade.timestamp.desc()).limit(4).all()
            recent_f_coinm = db.query(models.FuturesCoinmTrade).order_by(models.FuturesCoinmTrade.timestamp.desc()).limit(4).all()

            payload = {
                "type":"market_snapshot",
                "time": datetime.utcnow().isoformat(),
                "spot": [{"id": r.id, "pair": r.pair, "price": r.price, "amount": r.amount} for r in recent_spot],
                "futures_usdm": [{"id": r.id, "pair": r.pair, "price": r.price} for r in recent_f_usdm],
                "futures_coinm": [{"id": r.id, "pair": r.pair, "price": r.price} for r in recent_f_coinm],
            }
            await ws_manager.broadcast_json(payload)
        except Exception:
            # swallow and continue
            pass
        finally:
            try:
                db.close()
            except Exception:
                pass
        await asyncio.sleep(5)  # every 5 seconds

@app.on_event("startup")
async def startup_event():
    # start periodic broadcaster in background
    try:
        asyncio.create_task(market_snapshot_loop())
    except Exception:
        # if even create_task fails (unlikely in FastAPI), ignore
        pass
    print("🚀 Blockflow investor-demo backend started (Render-safe)")
 # ============================================================
# Market & Trade Feed APIs (for frontend live sync)
# ============================================================

@app.get("/api/trades")
def get_recent_trades(limit: int = 50):
    """Fetch latest trades across all markets"""
    with SessionLocal() as db:
        spot = db.query(models.SpotTrade).order_by(models.SpotTrade.timestamp.desc()).limit(limit).all()
        futures_usdm = db.query(models.FuturesUsdmTrade).order_by(models.FuturesUsdmTrade.timestamp.desc()).limit(limit).all()
        futures_coinm = db.query(models.FuturesCoinmTrade).order_by(models.FuturesCoinmTrade.timestamp.desc()).limit(limit).all()
        margin = db.query(models.MarginTrade).order_by(models.MarginTrade.timestamp.desc()).limit(limit).all()
        options = db.query(models.OptionsTrade).order_by(models.OptionsTrade.timestamp.desc()).limit(limit).all()
        data = {
            "spot": [t.as_dict() for t in spot],
            "margin": [t.as_dict() for t in margin],
            "futures_usdm": [t.as_dict() for t in futures_usdm],
            "futures_coinm": [t.as_dict() for t in futures_coinm],
            "options": [t.as_dict() for t in options],
        }
        return data


@app.get("/api/market/orderbook")
def get_orderbook():
    """Return latest simulated orderbook / prices"""
    try:
        from app.price_feed import latest_prices
        return {"orderbook": latest_prices}
    except Exception:
        return {"error": "price_feed not active yet"}


# --------------------------
# End file
# --------------------------


# ---------------- end file ----------------


