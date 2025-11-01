# app/wallet_service.py
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from app.models import WalletTransaction, User

class WalletService:
    def __init__(self, db: Session):
        self.db = db

    # ✅ Add funds to wallet
    def credit(self, user_id: int, asset: str, amount: float):
        tx = WalletTransaction(
            user_id=user_id,
            asset=asset,
            amount=amount,
            tx_type="credit",
            timestamp=datetime.utcnow()
        )
        self.db.add(tx)
        self.db.commit()
        self.db.refresh(tx)
        return tx

    # ✅ Deduct funds from wallet
    def debit(self, user_id: int, asset: str, amount: float):
        tx = WalletTransaction(
            user_id=user_id,
            asset=asset,
            amount=-abs(amount),
            tx_type="debit",
            timestamp=datetime.utcnow()
        )
        self.db.add(tx)
        self.db.commit()
        self.db.refresh(tx)
        return tx

    # ✅ Get all balances for user (SQLAlchemy 2.x safe)
    def get_all_balances(self, user_id: int):
        """
        Returns a list of {asset, balance} for a specific user.
        Uses text() to wrap SQL string for SQLAlchemy 2.x compliance.
        """
        result = self.db.execute(
            text("""
                SELECT asset, SUM(amount) AS balance
                FROM wallet_transactions
                WHERE user_id = :uid
                GROUP BY asset
            """),
            {"uid": user_id}
        )
        balances = [
            {"asset": row[0], "balance": float(row[1]) if row[1] is not None else 0.0}
            for row in result.fetchall()
        ]
        return balances

    # ✅ Ledger of all transactions
    def get_ledger(self, user_id: int):
        """
        Returns a transaction history for the user.
        """
        transactions = (
            self.db.query(WalletTransaction)
            .filter(WalletTransaction.user_id == user_id)
            .order_by(WalletTransaction.timestamp.desc())
            .limit(100)
            .all()
        )

        return [
            {
                "asset": tx.asset,
                "amount": tx.amount,
                "type": tx.tx_type,
                "timestamp": tx.timestamp.isoformat(),
            }
            for tx in transactions
        ]

    # ✅ Transfer between users
    def transfer(self, sender_id: int, receiver_id: int, asset: str, amount: float):
        """
        Performs a transfer: debit sender and credit receiver atomically.
        """
        try:
            sender_balance = self.get_user_balance(sender_id, asset)
            if sender_balance < amount:
                raise ValueError("Insufficient funds")

            self.debit(sender_id, asset, amount)
            self.credit(receiver_id, asset, amount)
            self.db.commit()
            return {"status": "success", "amount": amount, "asset": asset}
        except Exception as e:
            self.db.rollback()
            raise e

    # ✅ Helper: get single balance
    def get_user_balance(self, user_id: int, asset: str) -> float:
        """
        Returns the balance for one asset.
        """
        result = self.db.execute(
            text("""
                SELECT SUM(amount) FROM wallet_transactions
                WHERE user_id = :uid AND asset = :asset
            """),
            {"uid": user_id, "asset": asset}
        )
        balance = result.scalar()
        return float(balance) if balance else 0.0
