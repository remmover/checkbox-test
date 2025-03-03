import os
from decimal import Decimal
from typing import List, Tuple

import qrcode
from fastapi import HTTPException

from app.persistence.models import PaymentType, Receipt
from app.service.shemas import CalculatedProduct, ReceiptCreateRequest

BASE_URL = "http://localhost:8000"
TEXT_RECEIPT_DIR = "static/receipts"
QR_CODE_DIR = "static/qr"

os.makedirs(TEXT_RECEIPT_DIR, exist_ok=True)
os.makedirs(QR_CODE_DIR, exist_ok=True)


def generate_receipt_text(receipt: Receipt, line_length: int) -> str:
    seller_name = "ФОП Джонсонюк Борис"
    separator = "=" * line_length
    lines: List[str] = []

    # Header
    lines.append(seller_name.center(line_length))
    lines.append(separator)

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
    qr = qrcode.make(url)
    qr.save(file_path)


def calculate_receipt_details(receipt_request: ReceiptCreateRequest) -> Tuple[
    List[CalculatedProduct], Decimal, Decimal]:
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
