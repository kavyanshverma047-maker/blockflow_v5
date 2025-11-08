# app/routers/ws_market.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import random
from typing import Dict

router = APIRouter()

PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "MATICUSDT"]
BASE_PRICES = {
    "BTCUSDT": 60000.0, "ETHUSDT": 2500.0, "SOLUSDT": 50.0, "BNBUSDT": 350.0, "MATICUSDT": 1.2
}

# simple in-memory (per-process) price state — refreshed slowly
_price_state: Dict[str, float] = {p: BASE_PRICES[p] for p in PAIRS}

async def _tick_prices():
    # small random walk
    for p in PAIRS:
        drift = random.uniform(-0.002, 0.002)
        _price_state[p] = max(0.0001, _price_state[p] * (1 + drift))

@router.websocket("/ws/market")
async def ws_market(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await _tick_prices()
            payload = {"type": "market_update", "prices": {p: round(_price_state[p], 2) for p in PAIRS}}
            await websocket.send_json(payload)
            # broadcast every 1 second
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return
    except Exception as e:
        try:
            await websocket.close()
        except Exception:
            pass
        print("ws_market error:", repr(e))
