from sqlalchemy.orm import Session
from app.models import LedgerEntry, User
from typing import List


class LedgerService:
    def __init__(self, db: Session):
        self.db = db

    def get_ledger(self, user_id: int) -> List[LedgerEntry]:
        return (
            self.db.query(LedgerEntry)
            .filter(LedgerEntry.user_id == user_id)
            .order_by(LedgerEntry.created_at.desc())
            .all()
        )

    def get_ledger_by_asset(self, user_id: int, asset: str) -> List[LedgerEntry]:
        return (
            self.db.query(LedgerEntry)
            .filter(
                LedgerEntry.user_id == user_id,
                LedgerEntry.asset == asset.upper()
            )
            .order_by(LedgerEntry.created_at.desc())
            .all()
        )

