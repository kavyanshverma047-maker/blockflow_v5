# app/models.py
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(String, nullable=True)  # placeholder (no real hashing required in demo)
    balance = Column(Float, default=100000.0)  # demo balance

    orders = relationship("P2POrder", back_populates="user")
    trades = relationship("Trade", back_populates="user")


class P2POrder(Base):
    __tablename__ = "p2p_orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String, nullable=False)  # 'Buy' or 'Sell'
    merchant = Column(String, nullable=True)
    price = Column(Float, nullable=False)
    available = Column(Float, nullable=False)  # BTC amount available
    limit_min = Column(Float, nullable=True)
    limit_max = Column(Float, nullable=True)
    payment_method = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="orders")


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    seller_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    price = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)  # BTC traded
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="trades", foreign_keys=[buyer_id])

