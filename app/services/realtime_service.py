
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict


class WebSocketManager:
    """Handles live WebSocket connections for real-time updates"""

    def __init__(self):
        # Active connections: user_id → WebSocket
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        """Accept and store a new WebSocket connection"""
        await websocket.accept()
        self.active_connections[user_id] = websocket

    async def disconnect(self, user_id: str):
        """Remove WebSocket connection when user disconnects"""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].close()
            except Exception:
                pass
            finally:
                del self.active_connections[user_id]

    async def send_to_user(self, user_id: str, message: dict):
        """Send message to a specific connected user"""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
            except WebSocketDisconnect:
                await self.disconnect(user_id)

    async def broadcast(self, message: dict):
        """Broadcast message to all connected users"""
        disconnected = []
        for user_id, ws in self.active_connections.items():
            try:
                await ws.send_json(message)
            except WebSocketDisconnect:
                disconnected.append(user_id)
        # Clean up disconnected sockets
        for user_id in disconnected:
            await self.disconnect(user_id)


# Global instance for import
manager = WebSocketManager()
