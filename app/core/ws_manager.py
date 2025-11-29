import asyncio, json, time
from fastapi import WebSocket

class WebSocketManager:
    def __init__(self):
        self.conns = set()
        self.stats = {"total_connections":0,"active_connections":0,"total_messages_sent":0}
        self.lock = asyncio.Lock()

    async def subscribe(self, ws: WebSocket, channel="market"):
        await ws.accept()
        async with self.lock:
            self.conns.add((ws,channel))
            self.stats["total_connections"] += 1
            self.stats["active_connections"] = len(self.conns)
        # send welcome
        await ws.send_json({"type":"welcome","channel":channel,"ts":int(time.time()*1000)})

    async def unsubscribe(self, ws):
        async with self.lock:
            # remove any matching ws entries
            self.conns = set([(c,ch) for (c,ch) in self.conns if c!=ws])
            self.stats["active_connections"] = len(self.conns)

    async def start_queue_forwarder(self, ws, queue, channel):
        # forward messages from market engine queue to websocket
        try:
            while True:
                msg = await queue.get()
                await ws.send_json(msg)
                self.stats["total_messages_sent"] += 1
        except Exception:
            try:
                await ws.close()
            except: pass

    def get_stats(self):
        return {"active_connections":self.stats["active_connections"], "total_connections":self.stats["total_connections"], "total_messages_sent":self.stats["total_messages_sent"]}
    
    async def close_all(self):
        async with self.lock:
            for ws, ch in list(self.conns):
                try:
                    await ws.close()
                except: pass
            self.conns.clear()
            self.stats["active_connections"]=0
