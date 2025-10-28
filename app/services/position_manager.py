from sqlalchemy.orm import Session
from app.models import FuturesUsdmTrade, FuturesCoinmTrade, LedgerEntry
from datetime import datetime

class PositionManager:
    def __init__(self, db: Session):
        self.db = db

    def calculate_pnl(self, position, current_price: float):
        """Calculate Unrealized PnL"""
        if position.side == "LONG":
            pnl = (current_price - position.entry_price) * position.size
        else:
            pnl = (position.entry_price - current_price) * position.size
        return round(pnl, 2)

    def update_positions(self, current_prices: dict):
        """Recalculate PnL for all open positions"""
        trades = self.db.query(FuturesUSDMTrade).filter(FuturesUSDMTrade.is_open == True).all()
        for t in trades:
            if t.pair in current_prices:
                t.unrealized_pnl = self.calculate_pnl(t, current_prices[t.pair])
                t.last_updated = datetime.utcnow()
        self.db.commit()

    def close_position(self, position_id: int, closing_price: float):
        """Close position and move PnL to ledger"""
        trade = self.db.query(FuturesUSDMTrade).get(position_id)
        if not trade:
            return None

        trade.realized_pnl = self.calculate_pnl(trade, closing_price)
        trade.is_open = False
        self.db.commit()

        # Log to ledger
        entry = LedgerEntry(
            user_id=trade.user_id,
            type="FUTURES_PNL",
            amount=trade.realized_pnl,
            timestamp=datetime.utcnow(),
            description=f"Closed {trade.pair} {trade.side} position at {closing_price}"
        )
        self.db.add(entry)
        self.db.commit()
        return trade

