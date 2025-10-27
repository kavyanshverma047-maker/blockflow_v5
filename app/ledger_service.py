# app/ledger_service.py
"""
Synchronous ledger service for Blockflow.
Provides atomic, concurrency-safe helpers to credit/debit/transfer balances
and to log trades/ledger entries.

Design notes:
- Uses SQLAlchemy Session (sync) and relies on caller to manage top-level transactions
  for complex flows where desired. Some helpers commit/refresh for convenience.
- Uses 'meta' column on LedgerEntry (JSON) to avoid SQLAlchemy reserved 'metadata'.
- Amounts stored as floats on LedgerEntry (models use Numeric for schema).
"""

from typing import Optional, Tuple, List, Any
from decimal import Decimal
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app import models

# supported assets for basic validation
SUPPORTED_ASSETS = {"USDT", "BTC", "ETH", "INR"}


class LedgerError(Exception):
    pass


def _normalize_amount(amount) -> Decimal:
    try:
        return Decimal(str(amount))
    except Exception:
        raise LedgerError("invalid amount")


def create_ledger_entry(
    db: Session,
    user_id: int,
    asset: str,
    amount: Decimal,
    entry_type: str,
    meta: Optional[dict] = None,
) -> models.LedgerEntry:
    """
    Create (but do not commit) a LedgerEntry row and return it.
    Caller may commit the session.
    """
    if asset not in SUPPORTED_ASSETS:
        raise LedgerError(f"unsupported asset '{asset}'")

    entry = models.LedgerEntry(
        user_id=user_id,
        asset=asset,
        amount=float(amount),
        type=entry_type,
        meta=meta or {},
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    db.flush()  # populate entry.id if needed by caller
    return entry


def credit_user_balance(
    db: Session,
    user_id: int,
    asset: str,
    amount: float,
    reason: str = "credit",
    meta: Optional[dict] = None,
    commit: bool = False,
) -> models.LedgerEntry:
    """
    Credit (increase) a user's balance for the specified asset.
    - Locks the user row with SELECT FOR UPDATE to avoid races.
    - Returns the created ledger entry (not always committed unless commit=True).
    """
    amount_dec = _normalize_amount(amount)
    if amount_dec <= 0:
        raise LedgerError("credit amount must be positive")

    # Lock user row
    user = db.execute(
        select(models.User).where(models.User.id == user_id).with_for_update()
    ).scalar_one_or_none()
    if user is None:
        raise LedgerError("user not found")

    balance_field = f"balance_{asset.lower()}"
    if not hasattr(user, balance_field):
        raise LedgerError(f"user missing balance field '{balance_field}'")

    current = Decimal(str(getattr(user, balance_field) or 0))
    new_balance = current + amount_dec
    setattr(user, balance_field, float(new_balance))

    entry = create_ledger_entry(db, user_id, asset, amount_dec, reason, meta)
    # persist balance snapshot to entry
    entry.balance_after = float(new_balance)
    db.add(entry)

    if commit:
        try:
            db.commit()
            db.refresh(entry)
        except SQLAlchemyError as e:
            db.rollback()
            raise LedgerError(f"db commit failed: {e}")

    return entry


def debit_user_balance(
    db: Session,
    user_id: int,
    asset: str,
    amount: float,
    reason: str = "debit",
    meta: Optional[dict] = None,
    allow_negative: bool = False,
    commit: bool = False,
) -> models.LedgerEntry:
    """
    Debit (decrease) a user's balance. Prevents overdraft unless allow_negative=True.
    """
    amount_dec = _normalize_amount(amount)
    if amount_dec <= 0:
        raise LedgerError("debit amount must be positive")

    user = db.execute(
        select(models.User).where(models.User.id == user_id).with_for_update()
    ).scalar_one_or_none()
    if user is None:
        raise LedgerError("user not found")

    balance_field = f"balance_{asset.lower()}"
    if not hasattr(user, balance_field):
        raise LedgerError(f"user missing balance field '{balance_field}'")

    current = Decimal(str(getattr(user, balance_field) or 0))
    new_balance = current - amount_dec
    if not allow_negative and new_balance < 0:
        raise LedgerError("insufficient balance")

    setattr(user, balance_field, float(new_balance))

    entry = create_ledger_entry(db, user_id, asset, -amount_dec, reason, meta)
    entry.balance_after = float(new_balance)
    db.add(entry)

    if commit:
        try:
            db.commit()
            db.refresh(entry)
        except SQLAlchemyError as e:
            db.rollback()
            raise LedgerError(f"db commit failed: {e}")

    return entry


def transfer_between_users(
    db: Session,
    from_user_id: int,
    to_user_id: int,
    asset: str,
    amount: float,
    meta: Optional[dict] = None,
    commit: bool = True,
) -> Tuple[models.LedgerEntry, models.LedgerEntry]:
    """
    Transfer amount from one user to another in a single database transaction.
    Locks both user rows in a deterministic order to avoid deadlocks.
    Returns (debit_entry, credit_entry).
    By default this helper commits (commit=True); set commit=False to let caller control transaction.
    """
    if from_user_id == to_user_id:
        raise LedgerError("cannot transfer to same user")
    amount_dec = _normalize_amount(amount)
    if amount_dec <= 0:
        raise LedgerError("transfer amount must be positive")

    first, second = (from_user_id, to_user_id) if from_user_id < to_user_id else (to_user_id, from_user_id)

    # Lock both user rows
    users = db.execute(
        select(models.User).where(models.User.id.in_([first, second])).with_for_update()
    ).scalars().all()

    if len(users) != 2:
        raise LedgerError("one or both users not found")

    # Perform operations in a DB transaction scope
    try:
        # Debit sender
        debit_entry = debit_user_balance(db, from_user_id, asset, float(amount_dec), reason="transfer_out", meta={**(meta or {}), "to": to_user_id}, commit=False)
        # Credit receiver
        credit_entry = credit_user_balance(db, to_user_id, asset, float(amount_dec), reason="transfer_in", meta={**(meta or {}), "from": from_user_id}, commit=False)

        if commit:
            db.commit()
            # refresh entries so caller can inspect ids, balance_after
            db.refresh(debit_entry)
            db.refresh(credit_entry)

        return debit_entry, credit_entry
    except SQLAlchemyError as e:
        db.rollback()
        raise LedgerError(f"transfer failed: {e}")


# Utility: get recent ledger entries for a user
def get_recent_ledger(db: Session, user_id: int, limit: int = 50) -> List[models.LedgerEntry]:
    q = select(models.LedgerEntry).where(models.LedgerEntry.user_id == user_id).order_by(models.LedgerEntry.created_at.desc()).limit(limit)
    return db.execute(q).scalars().all()


# Convenience functions used by app.main for trade logging / recent trades.
def log_trade(db: Session, user_id: Optional[int], asset: str, amount: float, side: str, price: Optional[float] = None, meta: Optional[dict] = None) -> models.LedgerEntry:
    """
    Log a trade-related ledger entry. This does not alter user wallet balances by default.
    It's primarily a structured way to keep trade history in LedgerEntry table for PoR / audit.
    If user_id provided, attaches the trade to that user.
    """
    entry_meta = meta.copy() if isinstance(meta, dict) else {}
    entry_meta.update({"side": side, "price": price})
    entry = create_ledger_entry(db, user_id if user_id is not None else 0, asset, Decimal(str(amount)), entry_type="trade", meta=entry_meta)
    # caller likely wants the entry to be persisted
    db.commit()
    db.refresh(entry)
    return entry


def get_recent_trades(db: Session, symbol: Optional[str] = None, limit: int = 100) -> List[Any]:
    """
    Return recent SpotTrade rows (used by app.main). Falls back to empty list if SpotTrade is missing.
    """
    try:
        q = select(models.SpotTrade)
        if symbol:
            q = q.where(models.SpotTrade.pair == symbol)
        q = q.order_by(models.SpotTrade.timestamp.desc()).limit(limit)
        return db.execute(q).scalars().all()
    except Exception:
        return []



