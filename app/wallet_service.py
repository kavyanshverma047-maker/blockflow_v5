# app/wallet_service.py
from typing import Optional, List
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import NoResultFound

from . import models
from .schemas import LedgerEntryRead  # optional reuse of a common schema if you have one

class WalletService:
    def __init__(self):
        pass

    async def _ensure_user_exists(self, session: AsyncSession, user_id: int) -> models.User:
        q = select(models.User).where(models.User.id == user_id)
        result = await session.execute(q)
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError(f"user {user_id} not found")
        return user

    async def deposit(self, session: AsyncSession, user_id: int, asset: str, amount: Decimal, *, metadata: Optional[dict] = None):
        """
        Deposit: credit user's balance and create ledger entry via ledger_service.
        """
        if amount <= 0:
            raise ValueError("deposit amount must be > 0")

        # lazy import to avoid circular imports
        from . import ledger_service

        # validate user exists
        await self._ensure_user_exists(session, user_id)

        # run using provided session/transaction so ledger and wallet updates are atomic
        async with session.begin():
            entry = await ledger_service.credit_user_balance(
                session=session,
                user_id=user_id,
                asset=asset,
                amount=amount,
                metadata=metadata or {"type": "deposit"}
            )
        return entry

    async def withdraw(self, session: AsyncSession, user_id: int, asset: str, amount: Decimal, *, metadata: Optional[dict] = None):
        """
        Withdraw: debit user's balance (if sufficient) and create ledger entry via ledger_service.
        """
        if amount <= 0:
            raise ValueError("withdraw amount must be > 0")

        from . import ledger_service

        # validate user exists
        await self._ensure_user_exists(session, user_id)

        # optionally check balance first (ledger_service.debit_user_balance may already check)
        balance = await self.get_balance(session=session, user_id=user_id, asset=asset)
        if balance < amount:
            raise ValueError("insufficient balance")

        async with session.begin():
            entry = await ledger_service.debit_user_balance(
                session=session,
                user_id=user_id,
                asset=asset,
                amount=amount,
                metadata=metadata or {"type": "withdrawal"}
            )
        return entry

    async def transfer(self, session: AsyncSession, from_user_id: int, to_user_id: int, asset: str, amount: Decimal, *, metadata: Optional[dict] = None):
        """
        Internal transfer between users: atomic debit + credit and ledger entries creation via ledger_service.transfer_between_users.
        """
        if amount <= 0:
            raise ValueError("transfer amount must be > 0")
        if from_user_id == to_user_id:
            raise ValueError("from_user_id and to_user_id must differ")

        from . import ledger_service

        # ensure users exist
        await self._ensure_user_exists(session, from_user_id)
        await self._ensure_user_exists(session, to_user_id)

        async with session.begin():
            result = await ledger_service.transfer_between_users(
                session=session,
                from_user_id=from_user_id,
                to_user_id=to_user_id,
                asset=asset,
                amount=amount,
                metadata=metadata or {"type": "internal_transfer"}
            )
        return result

    async def get_balance(self, session: AsyncSession, user_id: int, asset: str) -> Decimal:
        """
        Return user's balance for an asset. Prefer ledger_service helper if available; otherwise compute from LedgerEntry sums.
        """
        # Try ledger_service.get_user_balance if exists
        try:
            from . import ledger_service
            if hasattr(ledger_service, "get_user_balance"):
                bal = await ledger_service.get_user_balance(session=session, user_id=user_id, asset=asset)
                return Decimal(bal)
        except Exception:
            # If ledger_service helper fails or doesn't exist, fall back to summing LedgerEntry
            pass

        # Fallback: compute from LedgerEntry rows
        q = (
            select(
                func.coalesce(func.sum(models.LedgerEntry.amount), 0)
            )
            .where(models.LedgerEntry.user_id == user_id)
            .where(models.LedgerEntry.asset == asset)
        )
        result = await session.execute(q)
        total = result.scalar_one()
        return Decimal(total or 0)

    async def get_ledger(self, session: AsyncSession, user_id: int, limit: int = 100, offset: int = 0) -> List[models.LedgerEntry]:
        q = (
            select(models.LedgerEntry)
            .where(models.LedgerEntry.user_id == user_id)
            .order_by(models.LedgerEntry.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(q)
        rows = result.scalars().all()
        return rows


