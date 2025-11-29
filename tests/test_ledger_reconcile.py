# tests/test_ledger_reconcile.py
import pytest
from decimal import Decimal
from app.db import Base, engine, SessionLocal
from app import wallet
from app.ledger import post_transaction
from app.models import Ledger, Wallet

@pytest.fixture(autouse=True)
def setup_database():
    """Create fresh database for each test"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_deposit_and_reserve_and_settle():
    """Test deposit, reserve, and settlement flow"""
    # 1. Deposit 1000 INR to user 1
    tx1 = wallet.deposit(1, 'INR', Decimal('1000'))
    assert tx1 is not None
    
    # Check wallet balance
    db = SessionLocal()
    try:
        w = db.query(Wallet).filter(
            Wallet.user_id == 1, 
            Wallet.currency == 'INR'
        ).first()
        assert w is not None
        assert w.available == Decimal('1000')
        assert w.reserved == Decimal('0')
        
        # 2. Reserve 100 INR
        tx2 = wallet.reserve(1, 'INR', Decimal('100'))
        assert tx2 is not None
        
        db.refresh(w)
        assert w.available == Decimal('900')
        assert w.reserved == Decimal('100')
        
        # 3. Settle 100 INR from user 1 to user 2 (no fee)
        tx3 = wallet.settle(1, 2, 'INR', Decimal('100'), fee=0)
        assert tx3 is not None
        
        # Check user 1 wallet
        db.refresh(w)
        assert w.available == Decimal('900')
        assert w.reserved == Decimal('0')
        
        # Check user 2 wallet
        w2 = db.query(Wallet).filter(
            Wallet.user_id == 2, 
            Wallet.currency == 'INR'
        ).first()
        assert w2 is not None
        assert w2.available == Decimal('100')
        assert w2.reserved == Decimal('0')
        
    finally:
        db.close()


def test_ledger_balance():
    """Test that ledger entries balance to zero"""
    wallet.deposit(1, 'INR', Decimal('500'))
    
    db = SessionLocal()
    try:
        # Get all ledger entries for the transaction
        ledger_entries = db.query(Ledger).all()
        
        # Sum should be zero (double-entry accounting)
        total = sum(Decimal(str(entry.amount)) for entry in ledger_entries)
        assert total == Decimal('0')
        
    finally:
        db.close()