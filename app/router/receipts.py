import os
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.persistence.connect import get_db
from app.persistence.models import User, PaymentType
from app.persistence.repository.receipts import create_receipt_in_db, fetch_receipts, fetch_receipt_by_id, \
    fetch_receipt_by_id_public
from app.service.auth import auth_service
from app.service.shemas import ReceiptResponse, ReceiptCreateRequest, ReceiptResponseOut, ReceiptItemResponse
from app.service.utils import calculate_receipt_details, generate_receipt_text, TEXT_RECEIPT_DIR, BASE_URL, QR_CODE_DIR, \
    generate_qr_code

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


@router.get("/public/receipt/{receipt_id}/download")
async def download_receipt_file(
    receipt_id: UUID,
    file_type: str = Query(..., description="Either 'txt' or 'qr'"),
    line_length: int = Query(40, gt=0, description="Number of characters per line"),
    db: AsyncSession = Depends(get_db),
):
    """
    Public endpoint that returns either the receipt text file or the QR code image,
    based on the 'file_type' query parameter. If necessary, it generates the files
    and saves them locally, then returns them via FileResponse.
    """
    if file_type not in ("txt", "qr"):
        raise HTTPException(status_code=400, detail="file_type must be 'txt' or 'qr'")

    # Fetch the receipt
    receipt = await fetch_receipt_by_id_public(db, receipt_id)

    # Check if the text or QR file paths are already stored in DB
    # Suppose our model has fields .text_file_path and .qr_file_path
    text_path = getattr(receipt, "text_file_path", None)
    qr_path = getattr(receipt, "qr_file_path", None)

    # If either file is missing, we generate them
    if not text_path or not qr_path:
        # Generate text
        receipt_text = generate_receipt_text(receipt, line_length)
        text_filename = f"{receipt.id}.txt"
        text_filepath = os.path.join(TEXT_RECEIPT_DIR, text_filename)

        with open(text_filepath, "w", encoding="utf-8") as f:
            f.write(receipt_text)

        # For the QR code, let's assume it encodes the text file's path or some URL
        qr_filename = f"{receipt.id}.png"
        qr_filepath = os.path.join(QR_CODE_DIR, qr_filename)

        # If you want the QR code to point to a local URL that serves the .txt, or any URL:
        # e.g., "http://localhost:8000/public/receipt/<id>/download?file_type=txt"
        # We'll create a direct link to the above route with the relevant param
        # For local usage or dev environment:
        txt_download_url = f"http://localhost:8000/public/receipt/{receipt.id}/download?file_type=txt"
        generate_qr_code(txt_download_url, qr_filepath)

        # Update DB fields
        receipt.text_file_path = text_filepath
        receipt.qr_file_path = qr_filepath
        db.add(receipt)
        await db.commit()
        await db.refresh(receipt)

        # Assign local variables so we can use them below
        text_path = text_filepath
        qr_path = qr_filepath

    # Return the requested file
    if file_type == "txt":
        if not os.path.isfile(text_path):
            raise HTTPException(status_code=404, detail="Text file not found on server")
        return FileResponse(
            path=text_path,
            media_type="text/plain",
            filename=os.path.basename(text_path),
        )
    else:
        if not os.path.isfile(qr_path):
            raise HTTPException(status_code=404, detail="QR file not found on server")
        return FileResponse(
            path=qr_path,
            media_type="image/png",
            filename=os.path.basename(qr_path),
        )