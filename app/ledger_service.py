"""
Ledger service - production-ready skeleton for ledger entries and balance updates.

Features:
- create_ledger_entry: writes a LedgerEntry row
- credit_user/debit_user: update user balance and log entry atomically
- transfer_between_users: atomic transfer between two users
- get_ledger_for_user / get_balance / reconcile helpers
- Defensive: transactional, rollback on errors, avoids circular imports by importing models inside functions.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# NOTE:
# We intentionally import models inside functions to avoid circular imports
# when models import services or other modules that import models.
# If your project already organizes imports so no circular import exists,
# you can move these imports to module level for slightly better performance.

# --- Helper / default metadata -----------------------------------------------------------------
def _now_iso():
    return datetime.utcnow().isoformat()

# --- Core operations ----------------------------------------------------------------------------
def create_ledger_entry(
    db: Session,
    user_id: Optional[int],
    asset: str,
    amount: float,
    entry_type: str,
    balance_before: Optional[float] = None,
    balance_after: Optional[float] = None,
    reference: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a LedgerEntry row. Does not change balances unless caller does so.
    Returns a dict representing the created entry.
    """
    # import local models lazily to avoid circular import
    from app.models import LedgerEntry

    if metadata is None:
        metadata = {}

    entry = LedgerEntry(
        user_id=user_id,
        asset=asset.upper(),
        amount=amount,
        type=entry_type,
        reference=reference,
        metadata=str(metadata),  # store as JSON string if column is String/Text. Adjust if JSON type available.
        balance_before=balance_before,
        balance_after=balance_after,
        timestamp=datetime.utcnow(),
    )

    db.add(entry)
    db.flush()  # get id assigned
    # return a simple mapping
    return {
        "id": getattr(entry, "id", None),
        "user_id": user_id,
        "asset": entry.asset,
        "amount": float(amount),
        "type": entry_type,
        "reference": reference,
        "metadata": metadata,
        "balance_before": balance_before,
        "balance_after": balance_after,
        "timestamp": entry.timestamp.isoformat(),
    }


def apply_balance_change(db: Session, user, asset: str, delta: float) -> float:
    """
    Apply a balance change for a user and return (new_balance).
    This function attempts to handle:
      1) If you have a dedicated column per asset (e.g. balance_usdt),
         you can add logic to map asset -> column.
      2) If you store balances in a dict/json column (user.balances), update it.
    Adjust this to match your User model storage.
    """
    asset = asset.upper()
    # try JSON/dict column `balances` (preferred)
    if hasattr(user, "balances") and isinstance(getattr(user, "balances"), dict):
        balances = user.balances or {}
        old = float(balances.get(asset, 0.0))
        new = old + float(delta)
        balances[asset] = new
        user.balances = balances
        return new

    # fallback mapping for typical columns (USDT/INR examples)
    col_map = {
        "USDT": "balance_usdt",
        "INR": "balance_inr",
        # add more mapping if you keep separate columns per asset, e.g. "BTC": "balance_btc"
    }
    if asset in col_map and hasattr(user, col_map[asset]):
        colname = col_map[asset]
        old = float(getattr(user, colname) or 0.0)
        new = old + float(delta)
        setattr(user, colname, new)
        return new

    # last resort: try generic `balance` field
    if hasattr(user, "balance"):
        old = float(getattr(user, "balance") or 0.0)
        new = old + float(delta)
        setattr(user, "balance", new)
        return new

    # if nothing matches, raise so developer notices
    raise AttributeError("Could not find balance storage on User model for asset: " + asset)


def credit_user(
    db: Session,
    user_id: int,
    asset: str,
    amount: float,
    reference: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Credit (increase) user balance and create ledger entry inside a transaction.
    """
    from app.models import User

    try:
        user = db.query(User).filter(User.id == user_id).with_for_update().one_or_none()
        if user is None:
            raise ValueError(f"User id={user_id} not found")

        before = None
        try:
            before = float(getattr(user, "balances", {}).get(asset.upper(), 0.0)) if hasattr(user, "balances") else None
        except Exception:
            before = None

        new_balance = apply_balance_change(db, user, asset, float(amount))
        entry = create_ledger_entry(
            db=db,
            user_id=user_id,
            asset=asset,
            amount=amount,
            entry_type="credit",
            balance_before=before,
            balance_after=new_balance,
            reference=reference,
            metadata=metadata,
        )
        db.commit()
        return entry
    except Exception:
        db.rollback()
        raise


def debit_user(
    db: Session,
    user_id: int,
    asset: str,
    amount: float,
    reference: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    allow_negative: bool = False,
) -> Dict[str, Any]:
    """
    Debit (decrease) user balance and create ledger entry.
    If allow_negative is False and insufficient funds, raises ValueError.
    """
    from app.models import User

    try:
        user = db.query(User).filter(User.id == user_id).with_for_update().one_or_none()
        if user is None:
            raise ValueError(f"User id={user_id} not found")

        # compute current balance (attempt balances dict first)
        current = 0.0
        if hasattr(user, "balances") and isinstance(getattr(user, "balances"), dict):
            current = float(user.balances.get(asset.upper(), 0.0))
        else:
            # fallback to mapped columns
            try:
                asset = asset.upper()
                col_map = {
                    "USDT": "balance_usdt",
                    "INR": "balance_inr",
                }
                if asset in col_map and hasattr(user, col_map[asset]):
                    current = float(getattr(user, col_map[asset]) or 0.0)
                else:
                    current = float(getattr(user, "balance", 0.0) or 0.0)
            except Exception:
                current = 0.0

        if not allow_negative and current < amount:
            raise ValueError(f"Insufficient funds for user {user_id}: have {current}, need {amount}")

        before = current
        new_balance = apply_balance_change(db, user, asset, -float(amount))
        entry = create_ledger_entry(
            db=db,
            user_id=user_id,
            asset=asset,
            amount=-abs(float(amount)),
            entry_type="debit",
            balance_before=before,
            balance_after=new_balance,
            reference=reference,
            metadata=metadata,
        )
        db.commit()
        return entry
    except Exception:
        db.rollback()
        raise


def transfer_between_users(
    db: Session,
    from_user_id: int,
    to_user_id: int,
    asset: str,
    amount: float,
    reference: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Atomic transfer: debit from_user, credit to_user, create two ledger entries.
    Returns a dict with both entries.
    """
    try:
        # We'll lock both users (order by id to avoid deadlocks)
        from app.models import User

        # ensure consistent locking order
        u1_id, u2_id = (from_user_id, to_user_id) if from_user_id <= to_user_id else (to_user_id, from_user_id)

        u1 = db.query(User).filter(User.id == u1_id).with_for_update().one_or_none()
        u2 = db.query(User).filter(User.id == u2_id).with_for_update().one_or_none()

        # map back to correct users
        user_from = u1 if u1.id == from_user_id else u2
        user_to = u2 if u2.id == to_user_id else u1

        if user_from is None or user_to is None:
            raise ValueError("One or both users not found for transfer")

        # Perform debit then credit
        # NOTE: using existing functions would open/commit transactions. Instead perform inline.
        # Check balance
        current_from = 0.0
        if hasattr(user_from, "balances") and isinstance(getattr(user_from, "balances"), dict):
            current_from = float(user_from.balances.get(asset.upper(), 0.0))
        else:
            col_map = {"USDT": "balance_usdt", "INR": "balance_inr"}
            if asset.upper() in col_map and hasattr(user_from, col_map[asset.upper()]):
                current_from = float(getattr(user_from, col_map[asset.upper()]) or 0.0)
            else:
                current_from = float(getattr(user_from, "balance", 0.0) or 0.0)

        if current_from < amount:
            raise ValueError(f"Insufficient funds for transfer: have {current_from}, need {amount}")

        before_from = current_from
        before_to = 0.0
        if hasattr(user_to, "balances") and isinstance(getattr(user_to, "balances"), dict):
            before_to = float(user_to.balances.get(asset.upper(), 0.0))
        else:
            col_map = {"USDT": "balance_usdt", "INR": "balance_inr"}
            if asset.upper() in col_map and hasattr(user_to, col_map[asset.upper()]):
                before_to = float(getattr(user_to, col_map[asset.upper()]) or 0.0)
            else:
                before_to = float(getattr(user_to, "balance", 0.0) or 0.0)

        # apply changes
        new_from = apply_balance_change(db, user_from, asset, -float(amount))
        new_to = apply_balance_change(db, user_to, asset, float(amount))

        # create ledger rows
        entry_out = create_ledger_entry(
            db=db,
            user_id=from_user_id,
            asset=asset,
            amount=-abs(float(amount)),
            entry_type="transfer_out",
            balance_before=before_from,
            balance_after=new_from,
            reference=reference,
            metadata=metadata,
        )
        entry_in = create_ledger_entry(
            db=db,
            user_id=to_user_id,
            asset=asset,
            amount=abs(float(amount)),
            entry_type="transfer_in",
            balance_before=before_to,
            balance_after=new_to,
            reference=reference,
            metadata=metadata,
        )

        db.commit()
        return {"out": entry_out, "in": entry_in}
    except Exception:
        db.rollback()
        raise


# --- Read helpers -------------------------------------------------------------------------------
def get_ledger_for_user(db: Session, user_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    from app.models import LedgerEntry

    rows = (
        db.query(LedgerEntry)
        .filter(LedgerEntry.user_id == user_id)
        .order_by(LedgerEntry.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "asset": r.asset,
            "amount": float(r.amount),
            "type": r.type,
            "reference": r.reference,
            "timestamp": r.timestamp.isoformat(),
            "balance_before": r.balance_before,
            "balance_after": r.balance_after,
            "metadata": r.metadata,
        }
        for r in rows
    ]


def get_balance(db: Session, user_id: int, asset: str) -> float:
    from app.models import User
    user = db.query(User).filter(User.id == user_id).one_or_none()
    if user is None:
        raise ValueError("User not found")
    if hasattr(user, "balances") and isinstance(user.balances, dict):
        return float(user.balances.get(asset.upper(), 0.0))
    col_map = {"USDT": "balance_usdt", "INR": "balance_inr"}
    if asset.upper() in col_map and hasattr(user, col_map[asset.upper()]):
        return float(getattr(user, col_map[asset.upper()]) or 0.0)
    return float(getattr(user, "balance", 0.0) or 0.0)


def reconcile_balance_from_ledger(db: Session, user_id: int, asset: str) -> float:
    """
    Recompute balance for a user+asset by summing ledger entries and optionally write back to User.
    Returns computed balance.
    """
    from app.models import LedgerEntry, User

    total = (
        db.query(LedgerEntry)
        .filter(LedgerEntry.user_id == user_id)
        .filter(LedgerEntry.asset == asset.upper())
        .with_entities(func.coalesce(func.sum(LedgerEntry.amount), 0.0))
        .scalar()
    )

    # optionally write back
    user = db.query(User).filter(User.id == user_id).one_or_none()
    if user:
        try:
            apply_balance_change(db, user, asset, total - get_balance(db, user_id, asset))
            db.commit()
        except Exception:
            db.rollback()
            raise

    return float(total)
