from decimal import Decimal
from typing import List, Tuple

from fastapi import HTTPException

from app.service.shemas import CalculatedProduct, ReceiptCreateRequest


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
