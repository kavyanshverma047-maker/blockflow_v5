from app.db import Base, engine, SessionLocal
from app import models, wallet
import pytest
from decimal import Decimal

@pytest.fixture(scope='module', autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_deposit_and_reserve_and_settle():
    # deposit to user 1 INR and reserve 100, then settle to user2
    wallet.deposit(1, 'INR', Decimal('1000'))
    wallet.deposit(2, 'INR', Decimal('100'))
    wallet.reserve(1, 'INR', Decimal('100'))
    # settle 50 from 1 to 2 with fee 1
    wallet.settle(1,2,'INR', Decimal('50'), fee=Decimal('1'))
    # run reconcile
    from demo.reconcile import reconcile
    inc = reconcile()
    assert inc == []  # no inconsistencies
