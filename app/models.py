from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# --- Users ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True)
    password = Column(String)
    balance_inr = Column(Float, default=100000)
    balance_usdt = Column(Float, default=1000)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# --- P2P Orders ---
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

# --- Spot Trades ---
class SpotTrade(Base):
    __tablename__ = "spot_trades"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String)
    pair = Column(String)
    side = Column(String)
    price = Column(Float)
    amount = Column(Float)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

# --- Margin Trades ---
class MarginTrade(Base):
    __tablename__ = "margin_trades"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String)
    pair = Column(String)
    side = Column(String)
    leverage = Column(Float, default=10)
    price = Column(Float)
    amount = Column(Float)
    pnl = Column(Float, default=0.0)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

# --- Futures (USDM) ---
class FuturesUsdmTrade(Base):
    __tablename__ = "futures_usdm_trades"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String)
    pair = Column(String)
    side = Column(String)
    leverage = Column(Float, default=20)
    price = Column(Float)
    amount = Column(Float)
    pnl = Column(Float, default=0.0)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

# --- Futures (COINM) ---
class FuturesCoinmTrade(Base):
    __tablename__ = "futures_coinm_trades"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String)
    pair = Column(String)
    side = Column(String)
    leverage = Column(Float, default=20)
    price = Column(Float)
    amount = Column(Float)
    pnl = Column(Float, default=0.0)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

# --- Options Trades ---
class OptionsTrade(Base):
    __tablename__ = "options_trades"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String)
    pair = Column(String)
    side = Column(String)
    strike = Column(Float)
    option_type = Column(String)  # call / put
    premium = Column(Float)
    size = Column(Float)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Define relationships explicitly
    buyer = relationship("User", back_populates="trades_as_buyer", foreign_keys=[buyer_id])
    seller = relationship("User", back_populates="trades_as_seller", foreign_keys=[seller_id])
