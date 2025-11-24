# app/models.py
"""
Blockflow Exchange - Database Models (FIXED v3.1)
==================================================
Production SQLAlchemy ORM models for crypto exchange backend.
Includes: User, UserAsset, RefreshToken, ApiKey, LedgerEntry, SpotTrade, FuturesUsdmTrade
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Numeric, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    """
    User model with INR balance embedded.
    Crypto balances (USDT, BTC, ETH, etc.) stored in UserAsset table.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    
    # Only INR balance lives in User table (fiat currency)
    balance_inr = Column(Numeric(20, 2), default=0.0, nullable=False)
    balance_usdt = Column(Numeric(20, 2), nullable=False, default=0)

    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user_assets = relationship("UserAsset", back_populates="user", cascade="all, delete-orphan")
    ledger_entries = relationship("LedgerEntry", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    
    # Trade relationships use username FK (not user_id) for flexibility
    spot_trades = relationship(
        "SpotTrade",
        back_populates="user",
        foreign_keys="[SpotTrade.username]",
        primaryjoin="User.username==SpotTrade.username"
    )
    futures_trades = relationship(
        "FuturesUsdmTrade",
        back_populates="user",
        foreign_keys="[FuturesUsdmTrade.username]",
        primaryjoin="User.username==FuturesUsdmTrade.username"
    )

    def __init__(self, **kwargs):
        """Backward compatibility: accept password, password_hash, or hashed_password"""
        if "password" in kwargs:
            kwargs["hashed_password"] = kwargs.pop("password")
        if "password_hash" in kwargs:
            kwargs["hashed_password"] = kwargs.pop("password_hash")
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"


class UserAsset(Base):
    """
    User's crypto asset balances (USDT, BTC, ETH, etc.)
    Replaces balance_usdt from User model to support multiple cryptocurrencies
    """
    __tablename__ = "user_assets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    asset = Column(String(20), nullable=False, index=True)  # "USDT", "BTC", "ETH", etc.
    balance = Column(Numeric(20, 8), default=0.0, nullable=False)  # 8 decimals for crypto precision
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Ensure one row per user-asset combination
    __table_args__ = (
        UniqueConstraint('user_id', 'asset', name='uq_user_asset'),
    )

    # Relationship
    user = relationship("User", back_populates="user_assets")

    def __repr__(self):
        return f"<UserAsset(user_id={self.user_id}, asset='{self.asset}', balance={self.balance})>"


class RefreshToken(Base):
    """JWT refresh tokens for auth system with database persistence"""
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(500), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)

    # Relationship
    user = relationship("User", back_populates="refresh_tokens")

    def __repr__(self):
        return f"<RefreshToken(id={self.id}, user_id={self.user_id})>"


class ApiKey(Base):
    """API keys for programmatic access"""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    user = relationship("User", back_populates="api_keys")

    def __repr__(self):
        return f"<ApiKey(id={self.id}, user_id={self.user_id})>"


class LedgerEntry(Base):
    """
    Audit log for all wallet transactions.
    Includes deposits, withdrawals, trades, TDS, etc.
    Supports both INR and crypto currencies.
    """
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    currency = Column(String(10), nullable=False, index=True)  # "INR", "USDT", "BTC", etc.
    amount = Column(Numeric(20, 8), nullable=False)  # Transaction amount (can be negative)
    balance_after = Column(Numeric(20, 8), nullable=False)  # Balance after this transaction
    txn_type = Column(String(50), nullable=False, index=True)  # deposit, withdraw, spot_trade, futures_trade, tds
    description = Column(Text, nullable=True)  # Human-readable description
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationship
    user = relationship("User", back_populates="ledger_entries")

    def __repr__(self):
        return f"<LedgerEntry(id={self.id}, user_id={self.user_id}, currency='{self.currency}', amount={self.amount})>"


class SpotTrade(Base):
    """
    Spot trading records (buy/sell crypto at current price).
    Uses username FK for flexibility (allows trades before full user setup).
    """
    __tablename__ = "spot_trades"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), ForeignKey("users.username", ondelete="CASCADE"), nullable=False, index=True)
    pair = Column(String(20), nullable=False, index=True)  # e.g., "BTCUSDT"
    side = Column(String(10), nullable=False)  # "buy" or "sell"
    price = Column(Numeric(20, 8), nullable=False)  # Execution price (8 decimals for crypto precision)
    amount = Column(Numeric(20, 8), nullable=False)  # Trade size
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationship
    user = relationship("User", back_populates="spot_trades", foreign_keys=[username])

    def __repr__(self):
        return f"<SpotTrade(id={self.id}, username='{self.username}', pair='{self.pair}', side='{self.side}')>"


class FuturesUsdmTrade(Base):
    """
    Futures trading (USDT-margined) with leverage and PnL tracking.
    Supports up to 125x leverage with proper margin and liquidation calculation.
    """
    __tablename__ = "futures_usdm_trades"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), ForeignKey("users.username", ondelete="CASCADE"), nullable=False, index=True)
    pair = Column(String(20), nullable=False, index=True)  # e.g., "BTCUSDT"
    side = Column(String(10), nullable=False)  # "buy" (long) or "sell" (short)
    price = Column(Numeric(20, 8), nullable=False)  # Entry price
    amount = Column(Numeric(20, 8), nullable=False)  # Position size
    leverage = Column(Numeric(10, 2), default=20.0, nullable=False)  # 1x to 125x leverage
    pnl = Column(Numeric(20, 8), default=0.0, nullable=False)  # Profit/Loss (updated on close or mark-to-market)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationship
    user = relationship("User", back_populates="futures_trades", foreign_keys=[username])

    def __repr__(self):
        return f"<FuturesUsdmTrade(id={self.id}, username='{self.username}', pair='{self.pair}', leverage={self.leverage}x)>"