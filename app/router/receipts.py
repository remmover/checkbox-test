from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.persistence.connect import get_db
from app.persistence.models import User, PaymentType
from app.persistence.repository.receipts import create_receipt_in_db, fetch_receipts, fetch_receipt_by_id
from app.service.auth import auth_service
from app.service.shemas import ReceiptResponse, ReceiptCreateRequest, ReceiptListResponse, ReceiptResponseOut, \
    ReceiptItemResponse
from app.service.utils import calculate_receipt_details

router = APIRouter(prefix="/receipt", tags=["receipt"])


# TODO: if card amount dont need
@router.post("/receipt", response_model=ReceiptResponse, status_code=status.HTTP_200_OK)
async def create_receipt(
    receipt_request: ReceiptCreateRequest,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a sales receipt for the authorized user.

    The function calculates the total per product, overall total,
    and rest (if payment is in cash). It then saves the receipt
    and its items to the database and returns the computed details.
    """
    calculated_products, total_sum, rest = calculate_receipt_details(receipt_request)

    new_receipt = await create_receipt_in_db(receipt_request, current_user, total_sum, db)

    response_data = ReceiptResponse(
        id=new_receipt.id,
        products=calculated_products,
        payment=receipt_request.payment,
        total=total_sum,
        rest=rest,
        created_at=new_receipt.created_at,
    )

    return response_data


@router.get("/receipts", response_model=List[ReceiptResponseOut], status_code=status.HTTP_200_OK)
async def list_receipts(
    start_date: Optional[datetime] = Query(
        None, description="Filter receipts created from this date (inclusive)"
    ),
    end_date: Optional[datetime] = Query(
        None, description="Filter receipts created up to this date (inclusive)"
    ),
    min_total: Optional[Decimal] = Query(
        None, description="Filter receipts with a total amount greater than or equal to this value"
    ),
    payment_type: Optional[str] = Query(
        None, description="Filter receipts by payment type (cash or card)"
    ),
    limit: int = Query(10, gt=0, description="Number of receipts per page"),
    offset: int = Query(0, ge=0, description="Number of receipts to skip"),
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    receipts = await fetch_receipts(
        db=db,
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
        min_total=min_total,
        payment_type=payment_type,
        limit=limit,
        offset=offset
    )

    response_data = []
    for receipt in receipts:
        if receipt.payment_type == PaymentType.card:
            paid_amount = receipt.total_amount
            rest = Decimal("0.00")
        else:
            paid_amount = receipt.paid_amount
            rest = paid_amount - receipt.total_amount

        receipt_response = ReceiptResponseOut(
            id=receipt.id,
            products=[ReceiptItemResponse.from_orm(item) for item in receipt.items],
            payment_type=receipt.payment_type.value
            if hasattr(receipt.payment_type, "value")
            else receipt.payment_type,
            total=receipt.total_amount,
            paid_amount=paid_amount,
            rest=rest,
            created_at=receipt.created_at
        )
        response_data.append(receipt_response)

    return response_data


@router.get("/receipts/{receipt_id}", response_model=ReceiptResponseOut, status_code=status.HTTP_200_OK)
async def get_receipt(
    receipt_id: UUID,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    receipt = await fetch_receipt_by_id(db=db, user_id=current_user.id, receipt_id=receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    if receipt.payment_type == PaymentType.card:
        paid_amount = receipt.total_amount
        rest = Decimal("0.00")
    else:
        paid_amount = receipt.paid_amount
        rest = paid_amount - receipt.total_amount

    response_data = {
        "id": receipt.id,
        "products": receipt.items,
        "payment_type": receipt.payment_type.value if hasattr(receipt.payment_type, "value") else receipt.payment_type,
        "total": receipt.total_amount,
        "paid_amount": paid_amount,
        "rest": rest,
        "created_at": receipt.created_at,
    }
    return response_data
