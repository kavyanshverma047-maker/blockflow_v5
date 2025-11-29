from collections import defaultdict
from datetime import datetime
import asyncio, random

class MarketEngine:
    def __init__(self):
        self.orderbooks = defaultdict(lambda: {"bids": [], "asks": []})
        self.recent_trades = defaultdict(list)
        self.tickers = {}
        self.broadcast_queues = defaultdict(list)
        self.last_update = {}
        self._init_defaults()

    def _init_defaults(self):
        for pair, base in [("BTCUSDT", 95000.0), ("ETHUSDT", 3500.0), ("SOLUSDT", 180.0)]:
            bids = [(round(base - i*10,2), round(0.01 + i*0.001,6)) for i in range(1,21)]
            asks = [(round(base + i*10,2), round(0.01 + i*0.001,6)) for i in range(1,21)]
            self.orderbooks[pair]["bids"] = bids
            self.orderbooks[pair]["asks"] = asks
            self.tickers[pair] = {"pair":pair,"price":base,"volume":0,"change_24h":0,"timestamp":datetime.utcnow().isoformat()}
            self.last_update[pair] = datetime.utcnow()

    def apply_trade(self, trade):
        pair = trade.get("pair","BTCUSDT")
        price = float(trade.get("price",0))
        amount = float(trade.get("amount",0))
        side = trade.get("side","buy")
        self.recent_trades[pair].append(trade)
        self.tickers.setdefault(pair,{}).update({"price":price, "timestamp":datetime.utcnow().isoformat()})
        # very small orderbook adjustment
        if side=="buy":
            asks = self.orderbooks[pair]["asks"]
            if asks and abs(asks[0][0]-price) < 1.0:
                q = asks[0][1] - amount
                if q>0: asks[0]=(asks[0][0],round(q,6))
                else: asks.pop(0)
        else:
            bids = self.orderbooks[pair]["bids"]
            if bids and abs(bids[0][0]-price) < 1.0:
                q = bids[0][1] - amount
                if q>0: bids[0]=(bids[0][0],round(q,6))
                else: bids.pop(0)
        self.last_update[pair] = datetime.utcnow()
        # broadcast (non-blocking)
        asyncio.create_task(self._broadcast(pair, {"type":"trade","symbol":pair,"side":side,"price":price,"size":amount,"ts":int(datetime.utcnow().timestamp()*1000)}))

    def register_queue(self, pair="market"):
        q = asyncio.Queue(maxsize=1000)
        self.broadcast_queues[pair].append(q)
        return q

    def unregister_queue(self, pair, q):
        if q in self.broadcast_queues.get(pair,[]): self.broadcast_queues[pair].remove(q)

    async def _broadcast(self, pair, msg):
        dead=[]
        for q in (self.broadcast_queues.get(pair,[]) + self.broadcast_queues.get("market",[])):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                dead.append((pair,q))
        for p,q in dead:
            self.unregister_queue(p,q)

    def get_snapshot(self,pair):
        return {"pair":pair,"orderbook":self.orderbooks[pair],"ticker":self.tickers.get(pair,{}),"recent_trades":self.recent_trades[pair][-50:],"last_update":self.last_update.get(pair).isoformat() if pair in self.last_update else None}

    def health_check(self):
        return {"status":"healthy","pairs_tracked":list(self.orderbooks.keys()),"total_trades":sum(len(v) for v in self.recent_trades.values()),"active_queues":sum(len(v) for v in self.broadcast_queues.values())}
