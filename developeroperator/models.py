from datetime import datetime
import enum
from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
try:
  from .database import Base
except (ImportError, ValueError):
  from database import Base


class OrderStatus(str, enum.Enum):
    cancel = "cancel"
    confirm = "confirm"
    pending = "pending"
    delivered = "delivered"


class UserProfile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    phone_number = Column(String(30), nullable=True)
    password = Column(String(255), nullable=False)
    registered_date = Column(DateTime, default=datetime.utcnow, nullable=False)

    orders = relationship(
        "Order", back_populates="user", cascade="all, delete-orphan"
    )


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(100), nullable=False, index=True)
    store = Column(String(100), nullable=False)
    product_name = Column(String(150), nullable=False, index=True)
    price = Column(Float, nullable=False)
    created_date = Column(DateTime, default=datetime.utcnow, nullable=False)

    orders = relationship("Order", back_populates="product")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    status = Column(
        Enum(OrderStatus), default=OrderStatus.pending, nullable=False
    )
    created_date = Column(DateTime, default=datetime.utcnow, nullable=False)

    product = relationship("Product", back_populates="orders")
    user = relationship("UserProfile", back_populates="orders")
