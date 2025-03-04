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
from app.service.schemas import CalculatedProduct, ReceiptCreateSchema, ReceiptResponseOut, ReceiptItemResponse

TEXT_RECEIPT_DIR = "/app/static/text_receipts"
QR_CODE_DIR = "/app/static/qr_codes"


def generate_receipt_text(receipt: Receipt, line_length: int) -> str:
    """
    Generates a formatted textual representation of a receipt.

    :param receipt: The receipt object containing items, payment type, and totals.
    :type receipt: Receipt
    :param line_length: Number of characters per line in the generated text.
    :type line_length: int
    :return: A multiline string representing the formatted receipt text.
    :rtype: str
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

    :param url: The URL to be encoded in the QR code.
    :type url: str
    :param file_path: The path where the QR code image will be saved.
    :type file_path: str
    :raises IOError: If there's an issue writing the QR code to the file system.
    :raises Exception: Any unexpected error encountered by the qrcode library.
    """
    qr = qrcode.make(url)
    qr.save(file_path)


def calculate_receipt_details(receipt_request: ReceiptCreateSchema) -> Tuple[List[CalculatedProduct], Decimal, Decimal]:
    """
    Calculates details for a receipt, such as total price per product, overall total, and rest for cash payments.

    :param receipt_request: The receipt data including products and payment details.
    :type receipt_request: ReceiptCreateSchema
    :return: A tuple containing a list of CalculatedProduct, the total sum, and the rest.
    :rtype: Tuple[List[CalculatedProduct], Decimal, Decimal]
    :raises HTTPException: If the cash amount provided is insufficient (rest would be negative).
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
    Computes how much was actually paid and how much remains (rest).

    :param payment_type: The type of payment (card or cash).
    :type payment_type: PaymentType
    :param total_amount: The total amount of the receipt.
    :type total_amount: Decimal
    :param paid_amount: The amount actually paid for the receipt.
    :type paid_amount: Decimal
    :return: A tuple of (paid_amount, rest).
    :rtype: Tuple[Decimal, Decimal]
    """
    if payment_type == PaymentType.card:
        # For card, assume full payment has been made
        return total_amount, Decimal("0.00")
    else:
        # For cash, paid_amount is the actual paid amount
        return paid_amount, paid_amount - total_amount


def build_receipt_response_out(receipt: Receipt) -> ReceiptResponseOut:
    """
    Converts a receipt ORM object into a ReceiptResponseOut schema instance.

    :param receipt: A receipt ORM object, including related items and payment details.
    :type receipt: Receipt
    :return: The Pydantic response schema for the receipt.
    :rtype: ReceiptResponseOut
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
    Fetches a receipt by its public ID. If the corresponding text and QR code files do not exist,
    they are generated, stored in the database, and then returned.

    :param db: The asynchronous database session.
    :type db: AsyncSession
    :param receipt_id: The public identifier of the receipt.
    :type receipt_id: UUID
    :param line_length: Number of characters per line when generating the text file.
    :type line_length: int
    :return: A tuple containing the text file path and the QR code file path.
    :rtype: Tuple[str, str]
    :raises HTTPException: If the receipt does not exist.
    :raises IOError: If generating or writing the files fails.
    :raises Exception: For any unexpected error encountered while updating the database.
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
