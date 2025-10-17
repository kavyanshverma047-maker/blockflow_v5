<<<<<<< HEAD
# models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# -------------------------
# USER
# -------------------------
=======
# app/models.py
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Float
from app.database import Base

>>>>>>> 7f477dc (Initial commit for Blockflow backend with new models)
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
<<<<<<< HEAD
    email = Column(String, unique=True)
    password = Column(String)
    balance_inr = Column(Float, default=100000.0)
    balance_usdt = Column(Float, default=1000.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# -------------------------
# P2P ORDERS
# -------------------------
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

# -------------------------
# SPOT TRADES
# -------------------------
class SpotTrade(Base):
    __tablename__ = "spot_trades"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    pair = Column(String, index=True)
    side = Column(String)
    price = Column(Float)
    amount = Column(Float)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

# -------------------------
# MARGIN TRADES
# -------------------------
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

# -------------------------
# FUTURES (USDM)
# -------------------------
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

# -------------------------
# FUTURES (COINM)
# -------------------------
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

# -------------------------
# OPTIONS TRADES
# -------------------------
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
=======
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    balance = Column(Float, default=100000.0)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(String, nullable=True)
    balance = Column(Float, default=100000.0)

    # Relationships
    orders = relationship("P2POrder", back_populates="user")
    # two separate trade relationships
    trades_as_buyer = relationship("Trade", back_populates="buyer", foreign_keys="Trade.buyer_id")
    trades_as_seller = relationship("Trade", back_populates="seller", foreign_keys="Trade.seller_id")


class P2POrder(Base):
    __tablename__ = "p2p_orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String, nullable=False)  # "Buy" or "Sell"
    merchant = Column(String, nullable=True)
    price = Column(Float, nullable=False)
    available = Column(Float, nullable=False)
    limit_min = Column(Float, nullable=True)
    limit_max = Column(Float, nullable=True)
    payment_method = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="orders")


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    seller_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    price = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Define relationships explicitly
    buyer = relationship("User", back_populates="trades_as_buyer", foreign_keys=[buyer_id])
    seller = relationship("User", back_populates="trades_as_seller", foreign_keys=[seller_id])
>>>>>>> 7f477dc (Initial commit for Blockflow backend with new models)
