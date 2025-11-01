# app/routers/ws_user.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
from app.db import SessionLocal
from app.models import User
import random

router = APIRouter()

@router.websocket("/ws/user/{username}")
async def ws_user_portfolio(websocket: WebSocket, username: str):
    """
    Stream a user's portfolio snapshot every 1.5s.
    Frontend should connect with the username (or user id) after auth.
    """
    await websocket.accept()
    try:
        while True:
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.username == username).first()
                if not user:
                    await websocket.send_json({"type": "error", "message": "user not found"})
                    await asyncio.sleep(5)
                    continue

                portfolio = {
                    "balance_usdt": round(float(user.balance_usdt or 0.0), 2),
                    "open_positions": random.randint(0, 6),      # simulated count
                    "pnl": round(random.uniform(-500, 2000), 2)  # simulated PnL for demo
                }
                await websocket.send_json({"type": "user_update", "username": username, "portfolio": portfolio})
            finally:
                db.close()

            await asyncio.sleep(1.5)
    except WebSocketDisconnect:
        return
    except Exception as e:
        try:
            await websocket.close()
        except Exception:
            pass
        print("ws_user error:", repr(e))
