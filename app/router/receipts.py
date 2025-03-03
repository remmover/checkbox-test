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
from app.persistence.models import User
from app.persistence.repository.receipts import create_receipt_in_db, fetch_receipts, fetch_receipt_by_id
from app.service import messages
from app.service.auth import auth_service
from app.service.logger import logger
from app.service.shemas import ReceiptResponse, ReceiptCreateSchema, ReceiptResponseOut
from app.service.utils import calculate_receipt_details, prepare_receipt_files, build_receipt_response_out

router = APIRouter(prefix="/receipt", tags=["Receipt"])


@router.post("/create", response_model=ReceiptResponse, status_code=status.HTTP_200_OK)
async def create_receipt(
    receipt_request: ReceiptCreateSchema,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new receipt in the database using the provided schema data.

    Args:
        receipt_request (ReceiptCreateSchema): The data required to create a new receipt.
        current_user (User): The current authenticated user (injected by FastAPI).
        db (AsyncSession): The database session dependency.

    Returns:
        ReceiptResponse: A response object containing information about the newly created receipt.

    Raises:
        HTTPException:
            - Various HTTPExceptions if database or validation errors occur at a lower level.
            - 500: For any other unexpected error during receipt creation.
        Exception: Reraised after rollback if an unexpected error occurs.
    """
    try:
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

    except HTTPException as http_err:
        logger.exception("HTTP error while creating receipt: %s", http_err)
        raise http_err

    except Exception as err:
        logger.exception("Unexpected error while creating receipt: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=messages.CREATE_RECP_ERROR
        ) from err


@router.get("/get-with-filters", response_model=List[ReceiptResponseOut], status_code=status.HTTP_200_OK)
async def list_receipts(
    start_date: Optional[datetime] = Query(
        None, description="Filter receipts created from this date (inclusive)"
    ),
    end_date: Optional[datetime] = Query(
        None, description="Filter receipts created up to this date (inclusive)"
    ),
    min_total: Optional[Decimal] = Query(
        None, description="Filter receipts with a total >= this value"
    ),
    payment_type: Optional[str] = Query(
        None, description="Filter receipts by payment type (cash or card)"
    ),
    limit: int = Query(10, gt=0, description="Number of receipts per page"),
    offset: int = Query(0, ge=0, description="Number of receipts to skip"),
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List receipts belonging to the current user, with optional filters.

    Args:
        start_date (Optional[datetime]): Filter for receipts created on or after this date.
        end_date (Optional[datetime]): Filter for receipts created on or before this date.
        min_total (Optional[Decimal]): Filter for receipts with a total greater than or equal to this value.
        payment_type (Optional[str]): Filter for receipts based on payment type ('cash' or 'card').
        limit (int): Maximum number of receipts to return. Defaults to 10.
        offset (int): Number of receipts to skip for pagination. Defaults to 0.
        current_user (User): The current authenticated user (injected by FastAPI).
        db (AsyncSession): The database session dependency.

    Returns:
        List[ReceiptResponseOut]: A list of receipts matching the given filters.

    Raises:
        HTTPException:
            - Various HTTPExceptions if database or validation errors occur at a lower level.
            - 500: For any other unexpected error during receipt retrieval.
        Exception: Reraised after rollback if an unexpected error occurs.
    """
    try:
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
        return [build_receipt_response_out(r) for r in receipts]

    except HTTPException as http_err:
        logger.exception("HTTP error while listing receipts: %s", http_err)
        raise http_err

    except Exception as err:
        logger.exception("Unexpected error while listing receipts: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=messages.GET_RECP_ERROR
        ) from err


@router.get("/get-by-id/{receipt_id}", response_model=ReceiptResponseOut, status_code=status.HTTP_200_OK)
async def get_receipt(
    receipt_id: UUID,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve a specific receipt by its unique ID.

    Args:
        receipt_id (UUID): The unique identifier of the receipt to retrieve.
        current_user (User): The current authenticated user (injected by FastAPI).
        db (AsyncSession): The database session dependency.

    Returns:
        ReceiptResponseOut: The details of the requested receipt.

    Raises:
        HTTPException:
            - 404: If the receipt is not found.
            - Various other HTTPExceptions if database errors occur.
            - 500: For any other unexpected error during receipt retrieval.
        Exception: Reraised after rollback if an unexpected error occurs.
    """
    try:
        receipt = await fetch_receipt_by_id(db=db, user_id=current_user.id, receipt_id=receipt_id)
        if not receipt:
            raise HTTPException(status_code=404, detail=messages.RECEIPT_NOT_EXIST)

        return build_receipt_response_out(receipt)

    except HTTPException as http_err:
        logger.exception("HTTP error while fetching receipt by ID: %s", http_err)
        raise http_err

    except Exception as err:
        logger.exception("Unexpected error while fetching receipt by ID: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=messages.GET_RECP_ERROR
        ) from err


@router.get("/public/{receipt_id}/download")
async def download_receipt_file(
    receipt_id: UUID,
    file_type: str = Query(..., description="Either 'txt' or 'qr'"),
    line_length: int = Query(40, gt=0, description="Number of characters per line"),
    download: bool = Query(True, description="If true, force download; if false, view inline"),
    db: AsyncSession = Depends(get_db),
):
    """
    Download a text or QR file associated with a public receipt.

    If the files do not exist, they are generated, stored, and then returned.

    Args:
        receipt_id (UUID): The unique identifier of the public receipt.
        file_type (str): Specifies which file to download ('txt' or 'qr').
        line_length (int): Number of characters per line in the generated text file.
        download (bool): Whether to download,
        db (AsyncSession): The database session dependency.

    Returns:
        FileResponse: A file response containing either a .txt or .png (QR) file.

    Raises:
        HTTPException:
            - 400: If the file_type is not 'txt' or 'qr'.
            - 404: If the requested file is not found on the server after generation.
            - Various other HTTPExceptions if database errors occur.
            - 500: For any unexpected error during file preparation or retrieval.
        Exception: Reraised after rollback if an unexpected error occurs.

    """
    try:
        if file_type not in ("txt", "qr"):
            raise HTTPException(status_code=400, detail=messages.FILE_TYPE_ERROR)

        # 1. Prepare the files (fetch or generate if missing)
        text_path, qr_path = await prepare_receipt_files(db, receipt_id, line_length, download)

        # 2. Return the requested file
        file_path = text_path if file_type == "txt" else qr_path
        media_type = "text/plain" if file_type == "txt" else "image/png"

        if not os.path.isfile(file_path):
            raise HTTPException(
                status_code=404,
                detail=f"{file_type.upper()} file not found on server"
            )

        disposition_type = "attachment" if download else "inline"
        content_disposition = f"{disposition_type}; filename={os.path.basename(file_path)}"

        return FileResponse(
            path=file_path,
            media_type=media_type,
            headers={"Content-Disposition": content_disposition},
        )

    except HTTPException as http_err:
        logger.exception("HTTP error while downloading receipt file: %s", http_err)
        raise http_err

    except Exception as err:
        logger.exception("Unexpected error while downloading receipt file: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=messages.DOWNLOAD_URL_ERROR
        ) from err
