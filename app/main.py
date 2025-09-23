# main.py
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import uuid
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Blockflow Demo Futures API")

# Allow your frontend origin(s)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # change to your frontend origin in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory demo store (replace with DB in prod)
demo_balances: dict[str, float] = {}
futures_positions: dict[str, list[dict]] = {}

class TradeRequest(BaseModel):
    side: str                # "buy" or "sell"
    amount: float
    price: float
    leverage: Optional[int] = 3
    tp: Optional[float] = None
    sl: Optional[float] = None

@app.post("/futures/reset/{username}")
def reset_futures(username: str):
    """Create or reset demo user with default balance."""
    demo_balances[username] = 50_000.0
    futures_positions[username] = []
    return {"username": username, "balance": demo_balances[username]}

@app.post("/futures/trade/{username}")
def place_futures_trade(username: str, req: TradeRequest):
    """Place a demo futures trade (opens a position)."""
    if username not in demo_balances:
        raise HTTPException(status_code=404, detail="User not found")

    # basic margin calc and check
    margin_required = (req.price * req.amount) / max(1, req.leverage)
    if demo_balances[username] < margin_required:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    pos_id = str(uuid.uuid4())[:8]
    position = {
        "id": pos_id,
        "symbol": "BTCUSDT",
        "side": "long" if req.side == "buy" else "short",
        "size": req.amount,
        "entry": req.price,
        "mark": req.price,
        "leverage": req.leverage,
        "tp": req.tp,
        "sl": req.sl,
    }

    demo_balances[username] -= margin_required
    futures_positions.setdefault(username, []).append(position)
    return {"balance": demo_balances[username], "position": position}

@app.get("/futures/positions/{username}")
def get_positions(username: str):
    return futures_positions.get(username, [])

@app.post("/futures/update/{username}/{pos_id}")
def update_tp_sl(username: str, pos_id: str, tp: Optional[float] = Query(None), sl: Optional[float] = Query(None)):
    arr = futures_positions.get(username, [])
    for pos in arr:
        if pos["id"] == pos_id:
            if tp is not None:
                pos["tp"] = tp
            if sl is not None:
                pos["sl"] = sl
            return pos
    raise HTTPException(status_code=404, detail="Position not found")

@app.post("/futures/close/{username}/{pos_id}")
def close_position(username: str, pos_id: str, price: float):
    arr = futures_positions.get(username)
    if not arr:
        raise HTTPException(status_code=404, detail="User not found or no positions")
    for pos in list(arr):
        if pos["id"] == pos_id:
            arr.remove(pos)
            # simple pnl calc (long: (close-entry)*size, short: reverse)
            pnl = (price - pos["entry"]) * pos["size"]
            if pos["side"] == "short":
                pnl = -pnl
            # refund margin + pnl to balance
            margin = (pos["entry"] * pos["size"]) / max(1, pos["leverage"])
            demo_balances[username] = demo_balances.get(username, 0) + margin + pnl
            return {"balance": demo_balances[username], "realized_pnl": pnl}
    raise HTTPException(status_code=404, detail="Position not found")


   

