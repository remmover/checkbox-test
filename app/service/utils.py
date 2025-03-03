import os
from decimal import Decimal
from typing import List, Tuple
from uuid import UUID

import qrcode
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import PaymentType, Receipt
from app.persistence.repository.receipts import fetch_receipt_by_id_public
from app.service import messages
from app.service.shemas import CalculatedProduct, ReceiptCreateSchema, ReceiptResponseOut, ReceiptItemResponse

TEXT_RECEIPT_DIR = "/app/static/text_receipts"
QR_CODE_DIR = "/app/static/qr_codes"


def generate_receipt_text(receipt: Receipt, line_length: int) -> str:
    """
    Generates a formatted textual representation of a receipt.

    Args:
        receipt (Receipt): The receipt object containing items, payment type, and totals.
        line_length (int): Number of characters per line in the generated text.

    Returns:
        str: A multiline string representing the formatted receipt text.

    Raises:
        None: This function does not raise exceptions, but it can propagate others implicitly.
    """
    seller_name = "ФОП Джонсонюк Борис"
    separator = "=" * line_length
    lines: List[str] = [seller_name.center(line_length), separator]

    for item in receipt.items:
        product_total: Decimal = item.unit_price * item.quantity
        left_line1 = f"{item.unit_price:.2f} x {item.quantity}"
        right_line1 = f"{product_total:,.2f}"
        line1 = f"{left_line1:<{line_length - len(right_line1)}}{right_line1}"

        left_line2 = f"{item.product_name}"
        right_line2 = f"{product_total:,.2f}"
        line2 = f"{left_line2:<{line_length - len(right_line2)}}{right_line2}"

        lines.append(line1)
        lines.append(line2)
        lines.append("-" * line_length)

    lines.append(separator)
    total_str = f"{receipt.total_amount:,.2f}"
    total_line = f"{'СУМА':<{line_length - len(total_str)}}{total_str}"
    lines.append(total_line)

    if receipt.payment_type == PaymentType.card:
        payment_label = "Картка"
        payment_amount = receipt.total_amount
    else:
        payment_label = "Готівка"
        payment_amount = receipt.paid_amount

    payment_amount_str = f"{payment_amount:,.2f}"
    payment_line = f"{payment_label:<{line_length - len(payment_amount_str)}}{payment_amount_str}"
    lines.append(payment_line)

    if receipt.payment_type == PaymentType.card:
        change = Decimal("0.00")
    else:
        change = receipt.paid_amount - receipt.total_amount

    change_str = f"{change:,.2f}"
    change_line = f"{'Решта':<{line_length - len(change_str)}}{change_str}"
    lines.append(change_line)
    lines.append(separator)

    date_str = receipt.created_at.strftime("%d.%m.%Y %H:%M")
    lines.append(date_str.center(line_length))

    thank_you = "Дякуємо за покупку!"
    lines.append(thank_you.center(line_length))

    return "\n".join(lines)


def generate_qr_code(url: str, file_path: str):
    """
    Generates a QR code from the provided URL and saves it to a file.

    Args:
        url (str): The URL to be encoded in the QR code.
        file_path (str): The path where the QR code image will be saved.

    Raises:
        IOError: If there's an issue writing the QR code to the file system.
        Exception: Any unexpected error encountered by the qrcode library.
    """
    qr = qrcode.make(url)
    qr.save(file_path)


def calculate_receipt_details(receipt_request: ReceiptCreateSchema) -> Tuple[List[CalculatedProduct], Decimal, Decimal]:
    """
    Calculates details for a receipt, such as total price per product, overall total, and rest for cash payments.

    Args:
        receipt_request (ReceiptCreateSchema): The receipt data including products and payment details.

    Returns:
        Tuple[List[CalculatedProduct], Decimal, Decimal]:
            A tuple of (list of CalculatedProduct, total sum, rest).

    Raises:
        HTTPException(400): If the cash amount provided is insufficient (rest would be negative).
    """
    total_sum = Decimal("0.00")
    calculated_products: List[CalculatedProduct] = []

    for product in receipt_request.products:
        total = product.price * product.quantity
        total_sum += total
        calculated_product = CalculatedProduct(
            name=product.name,
            price=product.price,
            quantity=product.quantity,
            total=total
        )
        calculated_products.append(calculated_product)

    if receipt_request.payment.type == "cash":
        rest = receipt_request.payment.amount - total_sum
        if rest < 0:
            raise HTTPException(status_code=400, detail=messages.ERROR_MONEY)
    else:
        rest = Decimal("0.00")

    return calculated_products, total_sum, rest


def get_paid_and_rest(
    payment_type: PaymentType,
    total_amount: Decimal,
    paid_amount: Decimal
) -> Tuple[Decimal, Decimal]:
    """
    Compute how much was actually paid and how much remains (rest).

    Args:
        payment_type (PaymentType): The type of payment (card or cash).
        total_amount (Decimal): The total amount of the receipt.
        paid_amount (Decimal): The amount actually paid for the receipt.

    Returns:
        Tuple[Decimal, Decimal]: A tuple of (paid_amount, rest).

    Raises:
        None: This function does not raise exceptions, but can propagate others implicitly.
    """
    if payment_type == PaymentType.card:
        # For card, assume full payment has been made
        return total_amount, Decimal("0.00")
    else:
        # For cash, paid_amount is the actual paid amount
        return paid_amount, paid_amount - total_amount


def build_receipt_response_out(receipt: Receipt) -> ReceiptResponseOut:
    """
    Convert a receipt ORM object into a ReceiptResponseOut schema instance.

    Args:
        receipt (Receipt): A receipt ORM object, including related items and payment details.

    Returns:
        ReceiptResponseOut: The Pydantic response schema for the receipt.

    Raises:
        None: This function does not raise exceptions, but can propagate others implicitly.
    """
    paid_amount, rest = get_paid_and_rest(
        payment_type=receipt.payment_type,
        total_amount=receipt.total_amount,
        paid_amount=receipt.paid_amount
    )
    return ReceiptResponseOut(
        id=receipt.id,
        products=[ReceiptItemResponse.model_validate(item) for item in receipt.items],
        payment_type=(
            receipt.payment_type.value
            if hasattr(receipt.payment_type, "value")
            else receipt.payment_type
        ),
        total=receipt.total_amount,
        paid_amount=paid_amount,
        rest=rest,
        created_at=receipt.created_at
    )


async def prepare_receipt_files(
    db: AsyncSession,
    receipt_id: UUID,
    line_length: int
) -> Tuple[str, str]:
    """
    Fetches a receipt by its public ID. If the corresponding text/QR code files
    do not exist, they are generated, paths are stored in the DB, and finally returned.

    Args:
        db (AsyncSession): The async database session.
        receipt_id (UUID): The public identifier of the receipt.
        line_length (int): Number of characters per line when generating the text file.

    Returns:
        Tuple[str, str]: A tuple containing (text_path, qr_path).

    Raises:
        HTTPException(404): If the receipt doesn't exist.
        IOError: If generating or writing the files fails.
        Exception: Rolls back changes if an unexpected error occurs while updating DB.
    """
    receipt = await fetch_receipt_by_id_public(db, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail=messages.RECEIPT_NOT_EXIST)

    # Generate receipt text
    receipt_text = generate_receipt_text(receipt, line_length)

    # Create directories if they don't exist
    os.makedirs(TEXT_RECEIPT_DIR, exist_ok=True)
    os.makedirs(QR_CODE_DIR, exist_ok=True)

    # Build file paths
    text_filename = f"{receipt.id}.txt"
    text_filepath = os.path.join(TEXT_RECEIPT_DIR, text_filename)

    qr_filename = f"{receipt.id}.png"
    qr_filepath = os.path.join(QR_CODE_DIR, qr_filename)

    try:
        # Create the text file
        with open(text_filepath, "w", encoding="utf-8") as f:
            f.write(receipt_text)
    except IOError as io_err:
        raise io_err
    try:
        # Create the QR code
        txt_url = (
            f"http://0.0.0.0:8000/receipt/public/{receipt_id}/download?file_type=txt&line_length=40"
        )
        generate_qr_code(txt_url, qr_filepath)
    except Exception as gen_err:
        # Cleanup partial text file if needed
        if os.path.exists(text_filepath):
            os.remove(text_filepath)
        raise gen_err

    text_path = text_filepath
    qr_path = qr_filepath

    return text_path, qr_path
