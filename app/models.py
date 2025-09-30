# app/models.py
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

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
