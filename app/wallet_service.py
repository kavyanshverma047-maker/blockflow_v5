from sqlalchemy.orm import Session
from app.models import User, LedgerEntry
from datetime import datetime
from typing import Optional


class WalletService:
    def __init__(self, db: Session):
        self.db = db

    def get_balance(self, user_id: int, asset: str) -> float:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        return user.balances.get(asset.upper(), 0.0)

    def deposit(self, user_id: int, asset: str, amount: float):
        asset = asset.upper()
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        user.balances[asset] = user.balances.get(asset, 0.0) + amount

        # Ledger entry
        ledger_entry = LedgerEntry(
            user_id=user_id,
            asset=asset,
            amount=amount,
            entry_type="deposit",
            created_at=datetime.utcnow()
        )
        self.db.add(ledger_entry)
        self.db.commit()
        self.db.refresh(user)
        return user.balances[asset]

    def withdraw(self, user_id: int, asset: str, amount: float):
        asset = asset.upper()
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        current_balance = user.balances.get(asset, 0.0)
        if current_balance < amount:
            raise ValueError("Insufficient balance")

        user.balances[asset] = current_balance - amount

        ledger_entry = LedgerEntry(
            user_id=user_id,
            asset=asset,
            amount=-amount,
            entry_type="withdrawal",
            created_at=datetime.utcnow()
        )
        self.db.add(ledger_entry)
        self.db.commit()
        self.db.refresh(user)
        return user.balances[asset]

