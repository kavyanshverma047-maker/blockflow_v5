# app/models.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Float, func, JSON, Numeric
from sqlalchemy.orm import relationship
from app.db import Base

# =========================
# USER MODEL
# =========================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    password = Column(String, nullable=False)
    balance_usdt = Column(Numeric(24, 8), default=100000.0)
    balance_inr = Column(Numeric(24, 8), default=100000.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    ledger_entries = relationship("LedgerEntry", back_populates="user", cascade="all, delete-orphan")


# =========================
# P2P ORDERS
# =========================
class P2POrder(Base):
    __tablename__ = "p2p_orders"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String)
    asset = Column(String)
    price = Column(Float)
    amount = Column(Float)
    payment_method = Column(String)
    status = Column(String, default="open")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# =========================
# SPOT TRADES
# =========================
class SpotTrade(Base):
    __tablename__ = "spot_trades"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    pair = Column(String, index=True)
    side = Column(String)
    price = Column(Float)
    amount = Column(Float)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


# =========================
# MARGIN TRADES
# =========================
class MarginTrade(Base):
    __tablename__ = "margin_trades"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    pair = Column(String, index=True)
    side = Column(String)
    leverage = Column(Float, default=10.0)
    price = Column(Float)
    amount = Column(Float)
    pnl = Column(Float, default=0.0)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


# =========================
# FUTURES (USDM)
# =========================
class FuturesUsdmTrade(Base):
    __tablename__ = "futures_usdm_trades"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    pair = Column(String, index=True)
    side = Column(String)
    leverage = Column(Float, default=20.0)
    price = Column(Float)
    amount = Column(Float)
    pnl = Column(Float, default=0.0)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    is_open = Column(Boolean, default=True)


# =========================
# FUTURES (COINM)
# =========================
class FuturesCoinmTrade(Base):
    __tablename__ = "futures_coinm_trades"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    pair = Column(String, index=True)
    side = Column(String)
    leverage = Column(Float, default=20.0)
    price = Column(Float)
    amount = Column(Float)
    pnl = Column(Float, default=0.0)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


# =========================
# OPTIONS TRADES
# =========================
class OptionsTrade(Base):
    __tablename__ = "options_trades"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    pair = Column(String, index=True)
    side = Column(String)
    strike = Column(Float)
    option_type = Column(String)  # 'call' / 'put'
    premium = Column(Float)
    size = Column(Float)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


# =========================
# REFRESH TOKEN, API KEY
# =========================
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="refresh_tokens")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    active = Column(Boolean, default=True)

    user = relationship("User", back_populates="api_keys")


# =========================
# LEDGER ENTRIES (Wallet / Ledger)
# =========================
class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    asset = Column(String, nullable=False)               # e.g. "BTC", "ETH", "USDT"
    amount = Column(Numeric(24, 8), nullable=False)       # Positive for credit, negative for debit
    balance_after = Column(Numeric(24, 8), nullable=True) # store balance after txn
    type = Column(String, nullable=False)                # "deposit","withdrawal","trade","fee","transfer"
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="ledger_entries")


