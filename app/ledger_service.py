# app/ledger_service.py
"""
Production-grade ledger helpers for Blockflow.
"""

from typing import Optional, Tuple
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime

from app import models

SUPPORTED_ASSETS = {"USDT", "BTC", "ETH", "INR"}


class LedgerError(Exception):
    pass


def _normalize_amount(amount) -> Decimal:
    return Decimal(str(amount))


def create_ledger_entry(
    db: Session,
    user_id: int,
    asset: str,
    amount: Decimal,
    entry_type: str,
    metadata: Optional[dict] = None,
) -> models.LedgerEntry:
    """Create a ledger entry record."""
    if asset not in SUPPORTED_ASSETS:
        raise LedgerError(f"Unsupported asset '{asset}'")

    entry = models.LedgerEntry(
        user_id=user_id,
        asset=asset,
        amount=float(amount),
        type=entry_type,
        metadata=metadata or {},
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    return entry


def credit_user_balance(db: Session, user_id: int, asset: str, amount: float, reason="credit", metadata=None):
    """Credit user balance and record ledger entry."""
    amount_dec = _normalize_amount(amount)
    if amount_dec <= 0:
        raise LedgerError("Credit amount must be positive")

    user = db.execute(
        select(models.User).where(models.User.id == user_id).with_for_update()
    ).scalar_one_or_none()
    if not user:
        raise LedgerError("User not found")

    balance_field = f"balance_{asset.lower()}"
    if not hasattr(user, balance_field):
        raise LedgerError(f"User missing field {balance_field}")

    current = Decimal(str(getattr(user, balance_field) or 0))
    new_balance = current + amount_dec
    setattr(user, balance_field, float(new_balance))

    entry = create_ledger_entry(db, user_id, asset, amount_dec, reason, metadata)
    entry.balance_after = float(new_balance)
    db.add(entry)
    return entry


def debit_user_balance(db: Session, user_id: int, asset: str, amount: float, reason="debit", metadata=None, allow_negative=False):
    """Debit user balance and record ledger entry."""
    amount_dec = _normalize_amount(amount)
    if amount_dec <= 0:
        raise LedgerError("Debit amount must be positive")

    user = db.execute(
        select(models.User).where(models.User.id == user_id).with_for_update()
    ).scalar_one_or_none()
    if not user:
        raise LedgerError("User not found")

    balance_field = f"balance_{asset.lower()}"
    if not hasattr(user, balance_field):
        raise LedgerError(f"User missing field {balance_field}")

    current = Decimal(str(getattr(user, balance_field) or 0))
    new_balance = current - amount_dec
    if not allow_negative and new_balance < 0:
        raise LedgerError("Insufficient balance")

    setattr(user, balance_field, float(new_balance))

    entry = create_ledger_entry(db, user_id, asset, -amount_dec, reason, metadata)
    entry.balance_after = float(new_balance)
    db.add(entry)
    return entry


def transfer_between_users(
    db: Session, from_user: int, to_user: int, asset: str, amount: float, metadata=None
) -> Tuple[models.LedgerEntry, models.LedgerEntry]:
    """Atomic transfer between users."""
    if from_user == to_user:
        raise LedgerError("Cannot transfer to same user")

    amount_dec = _normalize_amount(amount)
    if amount_dec <= 0:
        raise LedgerError("Transfer amount must be positive")

    first, second = sorted([from_user, to_user])
    users = db.execute(
        select(models.User).where(models.User.id.in_([first, second])).with_for_update()
    ).scalars().all()

    if len(users) != 2:
        raise LedgerError("One or both users not found")

    try:
        # Perform both debit and credit in one transaction
        debit_entry = debit_user_balance(
            db, from_user, asset, float(amount_dec), reason="transfer_out", metadata=metadata
        )
        credit_entry = credit_user_balance(
            db, to_user, asset, float(amount_dec), reason="transfer_in", metadata=metadata
        )
        db.commit()
        db.refresh(debit_entry)
        db.refresh(credit_entry)
        return debit_entry, credit_entry
    except Exception as e:
        db.rollback()
        raise LedgerError(str(e))


