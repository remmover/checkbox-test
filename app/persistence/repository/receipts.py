from datetime import datetime
from decimal import Decimal
from typing import Tuple, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.persistence.models import User, Receipt, PaymentType, ReceiptItem
from app.service.shemas import ReceiptCreateRequest


async def create_receipt_in_db(
    receipt_request: ReceiptCreateRequest,
    current_user: User,
    total_sum: Decimal,
    db: AsyncSession
) -> Receipt:
    """
    Save the receipt and its associated items into the database.
    """
    new_receipt = Receipt(
        user_id=current_user.id,
        payment_type=PaymentType(receipt_request.payment.type),
        total_amount=total_sum,
        paid_amount=receipt_request.payment.amount if receipt_request.payment.type == "cash" else None
    )
    db.add(new_receipt)
    await db.flush()

    for product in receipt_request.products:
        new_item = ReceiptItem(
            receipt_id=new_receipt.id,
            product_name=product.name,
            unit_price=product.price,
            quantity=product.quantity
        )
        db.add(new_item)

    await db.commit()
    await db.refresh(new_receipt)
    return new_receipt


async def fetch_receipts(
    db: AsyncSession,
    user_id: UUID,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    min_total: Optional[Decimal] = None,
    payment_type: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
) -> List[Receipt]:
    """
    Fetch receipts from the database applying filters and pagination.
    """
    query = select(Receipt).options(selectinload(Receipt.items)).where(
        Receipt.user_id == user_id
    )
    if start_date:
        query = query.where(Receipt.created_at >= start_date)
    if end_date:
        query = query.where(Receipt.created_at <= end_date)
    if min_total:
        query = query.where(Receipt.total_amount >= min_total)
    if payment_type:
        query = query.where(Receipt.payment_type == PaymentType(payment_type))
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def fetch_receipt_by_id(
    db: AsyncSession,
    user_id: UUID,
    receipt_id: UUID
):
    query = select(Receipt).options(selectinload(Receipt.items)).where(
        Receipt.id == receipt_id,
        Receipt.user_id == user_id
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def fetch_receipt_by_id_public(db: AsyncSession, receipt_id: UUID) -> Receipt:
    """
    Fetch a receipt by its ID without requiring authentication.
    """
    query = select(Receipt).options(selectinload(Receipt.items)).where(Receipt.id == receipt_id)
    result = await db.execute(query)
    receipt = result.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt
