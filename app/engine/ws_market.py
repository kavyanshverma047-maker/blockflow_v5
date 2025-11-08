# app/engine/ws_market.py
"""
Blockflow WebSocket Market Stream
---------------------------------
✅ Real-time market feed for frontend
✅ Compatible with Next.js useMarketFeed hook
✅ Optimized for Render free-tier stability
"""

import asyncio
import json
import random
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# Available trading pairs
PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "MATICUSDT"]


class MarketManager:
    """Manages active WebSocket connections and broadcasting"""

    def __init__(self):
        self.connections = set()

    async def connect(self, ws: WebSocket):
        """Accept and store a new WebSocket connection"""
        await ws.accept()
        self.connections.add(ws)

    async def disconnect(self, ws: WebSocket):
        """Remove a disconnected client"""
        self.connections.discard(ws)

    async def broadcast(self, payload: dict):
        """Broadcast a JSON message to all connected clients"""
        message = json.dumps(payload)
        for ws in list(self.connections):
            try:
                await ws.send_text(message)
            except WebSocketDisconnect:
                await self.disconnect(ws)
            except Exception:
                # Handle unexpected send errors silently
                await self.disconnect(ws)


manager = MarketManager()


@router.websocket("/ws/market")
async def market_ws(ws: WebSocket):
    """
    WebSocket endpoint:
    - Sends an initial handshake message ("subscribed")
    - Continuously pushes simulated market data every 2 seconds
    """
    await manager.connect(ws)
    await ws.send_json({
        "type": "subscribed",
        "message": "Connected to Blockflow market feed",
    })

    try:
        while True:
            # Simulate live market updates
            updates = []
            for p in PAIRS:
                # Generate realistic mock data
                base_price = 68000 if p == "BTCUSDT" else (
                    2400 if p == "ETHUSDT" else random.uniform(0.2, 150))
                price = round(base_price * (1 + random.uniform(-0.005, 0.005)), 2)
                change = round(random.uniform(-2, 2), 2)
                volume = round(random.uniform(10, 500), 2)

                updates.append({
                    "pair": p,
                    "price": price,
                    "change": change,
                    "volume": volume,
                })

            # Broadcast to all connected clients
            await manager.broadcast({
                "type": "market_update",
                "timestamp": asyncio.get_event_loop().time(),
                "data": updates,
            })

            # Throttle frequency to avoid Render free-tier throttling
            await asyncio.sleep(2)

    except WebSocketDisconnect:
        await manager.disconnect(ws)
    except Exception as e:
        # Handle unexpected disconnects gracefully
        await manager.disconnect(ws)
        print(f"⚠️ WebSocket error: {e}")
