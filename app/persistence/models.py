import enum
from datetime import date
from typing import List, Optional

from sqlalchemy import (
    Integer,
    String,
    ForeignKey,
    Numeric,
    DateTime,
    Enum,
    func,
)
from sqlalchemy.orm import mapped_column, Mapped, relationship, DeclarativeBase


class Base(DeclarativeBase):
    pass


class PaymentType(enum.Enum):
    cash = "cash"
    card = "card"


# Модель користувача
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    login: Mapped[str] = mapped_column(String(250), nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[date] = mapped_column("created_at", DateTime, default=func.now())
    updated_at: Mapped[date] = mapped_column(
        "updated_at", DateTime, default=func.now(), onupdate=func.now()
    )
    refresh_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    receipts: Mapped[List["Receipt"]] = relationship("Receipt", back_populates="user")


class Receipt(Base):
    __tablename__ = "receipts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    payment_type: Mapped[PaymentType] = mapped_column(Enum(PaymentType), nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[date] = mapped_column("created_at", DateTime, default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="receipts")

    items: Mapped[List["ReceiptItem"]] = relationship(
        "ReceiptItem",
        back_populates="receipt",
        cascade="all, delete-orphan"
    )


class ReceiptItem(Base):
    __tablename__ = "receipt_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receipt_id: Mapped[int] = mapped_column(Integer, ForeignKey("receipts.id"), nullable=False)
    product_name: Mapped[str] = mapped_column(String(250), nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    # Зв'язок з чеком
    receipt: Mapped["Receipt"] = relationship("Receipt", back_populates="items")
