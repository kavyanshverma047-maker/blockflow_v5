from sqlalchemy import Column, Integer, String, Numeric, DateTime, Enum, func, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
import enum
from .db import Base

class EntryType(enum.Enum):
    debit='debit'
    credit='credit'

class Ledger(Base):
    __tablename__='ledger'
    id=Column(Integer, primary_key=True, index=True)
    tx_id=Column(String, nullable=False)  # transaction identifier grouping entries
    account=Column(String, nullable=False) # e.g., user:1:INR:available or platform:fees:INR
    amount=Column(Numeric(36,18), nullable=False) # positive for credit to account, negative for debit (we'll use sign convention)
    entry_type=Column(Enum(EntryType), nullable=False)
    ref=Column(String, nullable=True)
    created_at=Column(DateTime(timezone=True), server_default=func.now())

class Wallet(Base):
    __tablename__='wallets'
    id=Column(Integer, primary_key=True, index=True)
    user_id=Column(Integer, nullable=False)
    currency=Column(String, nullable=False)
    available=Column(Numeric(36,18), default=0)
    reserved=Column(Numeric(36,18), default=0)

class Order(Base):
    __tablename__='orders'
    id=Column(Integer, primary_key=True, index=True)
    user_id=Column(Integer, nullable=False)
    market=Column(String, nullable=False)
    side=Column(String, nullable=False)
    price=Column(Numeric(36,18), nullable=True)
    quantity=Column(Numeric(36,18), nullable=False)
    remaining=Column(Numeric(36,18), nullable=False)
    status=Column(String, default='open')

class Trade(Base):
    __tablename__='trades'
    id=Column(Integer, primary_key=True, index=True)
    buy_order_id=Column(Integer, nullable=True)
    sell_order_id=Column(Integer, nullable=True)
    market=Column(String, nullable=False)
    price=Column(Numeric(36,18), nullable=False)
    quantity=Column(Numeric(36,18), nullable=False)
    timestamp=Column(DateTime(timezone=True), server_default=func.now())
