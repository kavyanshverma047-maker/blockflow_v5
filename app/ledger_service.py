"""
app/ledger_service.py
Production-grade ledger helpers for multi-asset balances.

Assumptions:
- models.User has numeric balance columns per asset or a generic balance table. This service
  uses a LedgerEntry model (id, user_id, asset, delta, balance_after, type, meta, created_at).
- app.database exposes `get_db()` (dependency that yields a SQLAlchemy Session) or `SessionLocal`.
  Adjust import if your project uses different names.
- All amounts are floats here for simplicity. For a production exchange please use integers (satoshis)
  or Decimal with context and column types adapted accordingly.
"""

from typing import Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

from app import models
from app.database import get_db  # change if your project exposes SessionLocal

# Optional: centralize supported assets
SUPPORTED_ASSETS = {"USDT", "BTC", "ETH", "USD"}

class LedgerError(Exception):
    pass


def _normalize_amount(amount) -> Decimal:
    """Return Decimal normalized amount (positive or negative)."""
    return Decimal(str(amount))


def create_ledger_entry(
    db: Session,
    user_id: int,
    asset: str,
    delta: Decimal,
    entry_type: str,
    meta: Optional[dict] = None,
) -> models.LedgerEntry:
    """
    Create a ledger entry and return it. Does NOT change any cached user balance field —
    higher-level helpers should update balances in the same transaction.
    """
    if asset not in SUPPORTED_ASSETS:
        raise LedgerError(f"Unsupported asset '{asset}'")

    entry = models.LedgerEntry(
        user_id=user_id,
        asset=asset,
        delta=float(delta),
        type=entry_type,
        meta=str(meta) if meta is not None else None,
        created_at=datetime.utcnow(),
    )

    db.add(entry)
    db.flush()  # ensure entry.id is populated
    return entry


def credit_user_balance(db: Session, user_id: int, asset: str, amount: float, reason="credit", meta=None):
    """
    Credit user's balance for an asset.
    - Uses SELECT FOR UPDATE on the user row for concurrency safety.
    - Creates a ledger entry.
    """
    amount_dec = _normalize_amount(amount)
    if amount_dec <= 0:
        raise LedgerError("Credit amount must be positive")

    # Lock the user row
    user = db.execute(
        select(models.User).where(models.User.id == user_id).with_for_update()
    ).scalar_one_or_none()

    if user is None:
        raise LedgerError("User not found")

    # calculate balance field for asset (example uses dynamic attribute "balance_<asset_lower>" if exists)
    balance_field = f"balance_{asset.lower()}"
    if hasattr(user, balance_field):
        current = Decimal(str(getattr(user, balance_field) or 0))
        new_balance = current + amount_dec
        setattr(user, balance_field, float(new_balance))
    else:
        # if you maintain balances in a separate table, update that table here
        # fallback: store last_balance on ledger entry only
        new_balance = None

    entry = create_ledger_entry(db, user_id, asset, amount_dec, entry_type=reason, meta=meta)
    # If you want to store resulting balance on entry:
    if new_balance is not None:
        entry.balance_after = float(new_balance)

    db.add(user)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def debit_user_balance(db: Session, user_id: int, asset: str, amount: float, reason="debit", meta=None, allow_negative=False):
    """
    Debit user balance with concurrency-safe locking and optional negative prevention.
    """
    amount_dec = _normalize_amount(amount)
    if amount_dec <= 0:
        raise LedgerError("Debit amount must be positive")

    user = db.execute(
        select(models.User).where(models.User.id == user_id).with_for_update()
    ).scalar_one_or_none()

    if user is None:
        raise LedgerError("User not found")

    balance_field = f"balance_{asset.lower()}"
    if hasattr(user, balance_field):
        current = Decimal(str(getattr(user, balance_field) or 0))
        new_balance = current - amount_dec
        if not allow_negative and new_balance < 0:
            raise LedgerError("Insufficient balance")
        setattr(user, balance_field, float(new_balance))
    else:
        new_balance = None

    entry = create_ledger_entry(db, user_id, asset, -amount_dec, entry_type=reason, meta=meta)
    if new_balance is not None:
        entry.balance_after = float(new_balance)

    db.add(user)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def transfer_between_users(db: Session, from_user: int, to_user: int, asset: str, amount: float, meta=None):
    """
    Transfer between two users in a single DB transaction. Locks both rows consistently.
    Uses deterministic order (lower id first) to avoid deadlocks.
    """
    if from_user == to_user:
        raise LedgerError("Cannot transfer to same user")

    amount_dec = _normalize_amount(amount)
    if amount_dec <= 0:
        raise LedgerError("Transfer amount must be positive")

    # Lock users in deterministic order
    first, second = (from_user, to_user) if from_user < to_user else (to_user, from_user)
    users = db.execute(
        select(models.User).where(models.User.id.in_([first, second])).with_for_update()
    ).scalars().all()

    # make sure both users present
    if len(users) != 2:
        raise LedgerError("One or both users not found")

    user_map = {u.id: u for u in users}
    sender = user_map[from_user]
    receiver = user_map[to_user]

    # Debit sender
    debit_entry = debit_user_balance(db, from_user, asset, float(amount_dec), reason="transfer_debit", meta=meta)
    # Credit receiver
    credit_entry = credit_user_balance(db, to_user, asset, float(amount_dec), reason="transfer_credit", meta=meta)

    return debit_entry, credit_entry


def get_recent_ledger(db: Session, user_id: int, limit: int = 50):
    q = select(models.LedgerEntry).where(models.LedgerEntry.user_id == user_id).order_by(models.LedgerEntry.created_at.desc()).limit(limit)
    return db.execute(q).scalars().all()


# If you prefer dependency-injection route handlers use get_db dependency and call these helpers.

