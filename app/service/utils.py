import os
from decimal import Decimal
from typing import List, Tuple

import qrcode
from fastapi import HTTPException

from app.persistence.models import PaymentType, Receipt
from app.service.shemas import CalculatedProduct, ReceiptCreateRequest

BASE_URL = "http://localhost:8000"  # Replace with your actual base URL
TEXT_RECEIPT_DIR = "static/receipts"
QR_CODE_DIR = "static/qr"

# Ensure that the directories exist
os.makedirs(TEXT_RECEIPT_DIR, exist_ok=True)
os.makedirs(QR_CODE_DIR, exist_ok=True)


def generate_receipt_text(receipt: Receipt, line_length: int) -> str:
    """
    Generate a text version of the receipt.
    Example output (using Ukrainian labels) may look like:

          ФОП Джонсонюк Борис
    ====================================
    3.00 x 298        870.00
    Mavic 3T          896,610.00
    ------------------------------------
    20.00 x 31       000.00
    Дрон FPV з акумулятором
    6S чорний         620,000.00
    ====================================
    СУМА             1,516,610.00
    Картка           1,516,610.00
    Решта                    0.00
    ====================================
           14.08.2023 14:42
         Дякуємо за покупку!
    """
    seller_name = "ФОП Джонсонюк Борис"
    separator = "=" * line_length
    lines: List[str] = []

    # Header
    lines.append(seller_name.center(line_length))
    lines.append(separator)

    # Receipt items
    # Assuming each receipt has an attribute `items` with properties:
    #   product_name, unit_price, quantity
    for item in receipt.items:
        product_total: Decimal = item.unit_price * item.quantity
        # Line 1: unit price and quantity on the left, subtotal right-aligned
        left_line1 = f"{item.unit_price:.2f} x {item.quantity}"
        right_line1 = f"{product_total:,.2f}"
        line1 = f"{left_line1:<{line_length - len(right_line1)}}{right_line1}"
        # Line 2: product name left-aligned, same subtotal right-aligned
        left_line2 = f"{item.product_name}"
        right_line2 = f"{product_total:,.2f}"
        line2 = f"{left_line2:<{line_length - len(right_line2)}}{right_line2}"
        lines.append(line1)
        lines.append(line2)
        lines.append("-" * line_length)

    # Summary section
    lines.append(separator)
    total_str = f"{receipt.total_amount:,.2f}"
    total_line = f"{'СУМА':<{line_length - len(total_str)}}{total_str}"
    lines.append(total_line)

    # Payment: if card then paid_amount equals total_amount; if cash, then paid_amount is stored and change calculated
    if receipt.payment_type == PaymentType.card:
        payment_label = "Картка"
        payment_amount = receipt.total_amount
    else:
        payment_label = "Готівка"
        payment_amount = receipt.paid_amount
    payment_amount_str = f"{payment_amount:,.2f}"
    payment_line = f"{payment_label:<{line_length - len(payment_amount_str)}}{payment_amount_str}"
    lines.append(payment_line)

    # Change line
    if receipt.payment_type == PaymentType.card:
        change = Decimal("0.00")
    else:
        change = receipt.paid_amount - receipt.total_amount
    change_str = f"{change:,.2f}"
    change_line = f"{'Решта':<{line_length - len(change_str)}}{change_str}"
    lines.append(change_line)
    lines.append(separator)

    # Date and thank-you message
    date_str = receipt.created_at.strftime("%d.%m.%Y %H:%M")
    lines.append(date_str.center(line_length))
    thank_you = "Дякуємо за покупку!"
    lines.append(thank_you.center(line_length))

    return "\n".join(lines)


def generate_qr_code(url: str, file_path: str):
    """
    Generate a QR code image for the given URL and save it to file_path.
    """
    qr = qrcode.make(url)
    qr.save(file_path)


def calculate_receipt_details(receipt_request: ReceiptCreateRequest) -> Tuple[
    List[CalculatedProduct], Decimal, Decimal]:
    """
    Calculate the total for each product, the overall total,
    and the change (rest) if the payment is made in cash.
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
            raise HTTPException(status_code=400, detail="Insufficient cash provided")
    else:
        rest = Decimal("0.00")

    return calculated_products, total_sum, rest
