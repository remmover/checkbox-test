from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.persistence.models import User, Receipt, PaymentType, ReceiptItem
from app.service import messages
from app.service.shemas import ReceiptCreateSchema


async def create_receipt_in_db(
    receipt_request: ReceiptCreateSchema,
    current_user: User,
    total_sum: Decimal,
    db: AsyncSession
) -> Receipt:
    """
    Create a new receipt record in the database.

    Args:
        receipt_request (ReceiptCreateSchema): The data schema for creating a receipt.
        current_user (User): The current authenticated user who owns the receipt.
        total_sum (Decimal): The total cost of all products in the receipt.
        db (AsyncSession): The async database session dependency.

    Returns:
        Receipt: The newly created receipt record.

    Raises:
        SQLAlchemyError: If an error occurs while committing the transaction to the database.
        Exception: For any unexpected errors that might occur during the creation process.
    """
    new_receipt = Receipt(
        user_id=current_user.id,
        payment_type=PaymentType(receipt_request.payment.type),
        total_amount=total_sum,
        paid_amount=(
            receipt_request.payment.amount
            if receipt_request.payment.type == "cash"
            else None
        )
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
    Retrieve a list of receipts matching various filter criteria.

    Args:
        db (AsyncSession): The async database session dependency.
        user_id (UUID): The ID of the user who owns the receipts.
        start_date (Optional[datetime]): Filters receipts created on or after this date.
        end_date (Optional[datetime]): Filters receipts created on or before this date.
        min_total (Optional[Decimal]): Filters receipts with a total amount >= this value.
        payment_type (Optional[str]): Filters receipts by payment type (e.g., 'cash' or 'card').
        limit (int): The maximum number of receipts to return (default is 10).
        offset (int): The number of receipts to skip before starting to collect the result set.

    Returns:
        List[Receipt]: A list of receipts matching the provided filters.

    Raises:
        SQLAlchemyError: If a database error occurs during the query execution.
        Exception: For any unexpected errors that might occur.
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
) -> Optional[Receipt]:
    """
    Retrieve a specific receipt by its ID for a given user.

    Args:
        db (AsyncSession): The async database session dependency.
        user_id (UUID): The ID of the user who owns the receipt.
        receipt_id (UUID): The unique identifier of the receipt.

    Returns:
        Optional[Receipt]: The corresponding receipt if found, otherwise None.

    Raises:
        SQLAlchemyError: If a database error occurs during the query execution.
        Exception: For any unexpected errors that might occur.
    """
    query = select(Receipt).options(selectinload(Receipt.items)).where(
        Receipt.id == receipt_id,
        Receipt.user_id == user_id
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def fetch_receipt_by_id_public(db: AsyncSession, receipt_id: UUID) -> Receipt:
    """
    Retrieve a public receipt by its unique ID (regardless of user).

    Args:
        db (AsyncSession): The async database session dependency.
        receipt_id (UUID): The unique identifier of the receipt.

    Returns:
        Receipt: The requested receipt if found.

    Raises:
        HTTPException(404): If the receipt is not found in the database.
        SQLAlchemyError: If a database error occurs during the query execution.
        Exception: For any unexpected errors that might occur.
    """
    query = select(Receipt).options(selectinload(Receipt.items)).where(
        Receipt.id == receipt_id
    )
    result = await db.execute(query)
    receipt = result.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail=messages.RECEIPT_NOT_EXIST)
    return receipt
