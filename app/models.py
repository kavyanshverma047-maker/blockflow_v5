# models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# -------------------------
# USER
# -------------------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
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
