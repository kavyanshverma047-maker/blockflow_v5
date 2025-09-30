from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    balance = Column(Float, default=100000.0)  # demo balance for prototype

    # Relationship: one user → many P2P orders
    orders = relationship("P2POrder", back_populates="user")


class P2POrder(Base):
    __tablename__ = "p2p_orders"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, nullable=False)              # Buy / Sell
    merchant = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    available = Column(Float, nullable=False)          # Amount of BTC/USDT available
    limit_min = Column(Float, nullable=False)          # Min trade limit
    limit_max = Column(Float, nullable=False)          # Max trade limit
    payment_method = Column(String, nullable=False)

    # Foreign key to User
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="orders")

    # Optional: add convenience property for username (read-only)
    @property
    def username(self):
        return self.user.username if self.user else None
