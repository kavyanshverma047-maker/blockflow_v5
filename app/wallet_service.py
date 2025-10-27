# app/wallet_service.py
from typing import Optional, List
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func
from app import models
from app import ledger_service


class WalletService:
    """Handles wallet operations by calling ledger_service functions."""

    def _ensure_user_exists(self, db: Session, user_id: int) -> models.User:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise ValueError(f"user {user_id} not found")
        return user

    def deposit(self, db: Session, user_id: int, asset: str, amount: Decimal, metadata: Optional[dict] = None):
        """Deposit (credit) user balance."""
        if amount <= 0:
            raise ValueError("Deposit amount must be > 0")

        self._ensure_user_exists(db, user_id)
        entry = ledger_service.credit_user_balance(
            db, user_id, asset, float(amount), reason="deposit", metadata=metadata
        )
        return entry

    def withdraw(self, db: Session, user_id: int, asset: str, amount: Decimal, metadata: Optional[dict] = None):
        """Withdraw (debit) user balance."""
        if amount <= 0:
            raise ValueError("Withdraw amount must be > 0")

        self._ensure_user_exists(db, user_id)
        entry = ledger_service.debit_user_balance(
            db, user_id, asset, float(amount), reason="withdraw", metadata=metadata
        )
        return entry

    def transfer(self, db: Session, from_user_id: int, to_user_id: int, asset: str, amount: Decimal, metadata: Optional[dict] = None):
        """Internal user-to-user transfer."""
        if amount <= 0:
            raise ValueError("Transfer amount must be > 0")
        if from_user_id == to_user_id:
            raise ValueError("Sender and receiver cannot be the same")

        self._ensure_user_exists(db, from_user_id)
        self._ensure_user_exists(db, to_user_id)

        debit_entry, credit_entry = ledger_service.transfer_between_users(
            db, from_user_id, to_user_id, asset, float(amount), metadata
        )
        return {"from_entry": debit_entry.id, "to_entry": credit_entry.id}

    def get_balance(self, db: Session, user_id: int, asset: str) -> Decimal:
        """Get total user balance for an asset."""
        q = db.query(func.coalesce(func.sum(models.LedgerEntry.amount), 0)).filter(
            models.LedgerEntry.user_id == user_id,
            models.LedgerEntry.asset == asset
        )
        total = q.scalar()
        return Decimal(total or 0)

    def get_ledger(self, db: Session, user_id: int, limit: int = 100, offset: int = 0) -> List[models.LedgerEntry]:
        """Fetch user ledger entries."""
        q = db.query(models.LedgerEntry).filter(
            models.LedgerEntry.user_id == user_id
        ).order_by(models.LedgerEntry.created_at.desc()).limit(limit).offset(offset)
        return q.all()
