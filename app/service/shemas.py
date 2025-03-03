from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator


from app.service import messages
from app.service.logger import logger


# =============================================================================
#                               Users
# =============================================================================

class UserSchema(BaseModel):
    """
    Schema for creating or updating a user.

    Attributes:
        name (str): The user's name (length between 5 and 16).
        login (str): The user's username/login.
        password (str): The user's password (length between 6 and 10).
    """
    name: str = Field(min_length=5, max_length=16)
    login: str
    password: str = Field(min_length=6, max_length=10)


class UserResponseSchema(BaseModel):
    """
    Response schema with basic user info.

    Attributes:
        id (UUID): The unique identifier of the user.
        login (str): The user's username/login.
    """
    id: UUID
    login: str

    model_config = ConfigDict(from_attributes=True)


class TokenModel(BaseModel):
    """
    Model containing authentication tokens.

    Attributes:
        access_token (str): The access token string.
        refresh_token (str): The refresh token string.
        token_type (str): The token type, defaults to 'bearer'.
    """
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# =============================================================================
#                             Products
# =============================================================================

class ProductBase(BaseModel):
    """
    Base model describing a product. Used to avoid duplication.
    """
    name: str
    price: Decimal
    quantity: int


class ProductItem(ProductBase):
    """
    A product item inherited from ProductBase, kept for backward compatibility
    or further extension.
    """
    # Inherits name, price, quantity directly from ProductBase
    pass


class CalculatedProduct(ProductBase):
    """
    A product with a computed 'total' field (price * quantity).
    """
    total: Decimal


class ReceiptItemResponse(BaseModel):
    """
    Simplified model for displaying an item within a receipt,
    using different field names from the base product for clarity.

    Attributes:
        product_name (str): The name of the product.
        unit_price (Decimal): The unit price of the product.
        quantity (int): The quantity of the product purchased.
    """
    product_name: str
    unit_price: Decimal
    quantity: int

    class Config:
        from_attributes = True


# =============================================================================
#                             Payment
# =============================================================================

class PaymentData(BaseModel):
    """
    Payment details for a transaction.

    Attributes:
        type (str): The type of payment, must be either 'cash' or 'card'.
        amount (Optional[Decimal]): Required if payment type is 'cash'.
    """
    type: str
    amount: Optional[Decimal] = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        """
        Validates the payment type (only 'cash' or 'card' are allowed).

        Raises:
            ValueError: If the payment type is invalid.
        """
        logger.debug("Validating payment type: %s", v)
        if v not in ("cash", "card"):
            logger.error(messages.INVALID_PAYMENT_TYPE)
            raise ValueError(messages.INVALID_PAYMENT_TYPE)
        return v

    @model_validator(mode="after")
    def check_cash_amount(self):
        """
        Validates that `amount` is provided if `type` is 'cash'.

        Raises:
            ValueError: If payment type is 'cash' but `amount` is None.
        """
        if self.type == "cash" and self.amount is None:
            logger.error(messages.AMOUNT_REQUIRED_FOR_CASH)
            raise ValueError(messages.AMOUNT_REQUIRED_FOR_CASH)
        return self


# =============================================================================
#                           Receipt Requests
# =============================================================================

class ReceiptCreateSchema(BaseModel):
    """
    Schema for creating a new receipt.

    Attributes:
        products (List[ProductItem]): List of product items in the receipt.
        payment (PaymentData): Payment information for this receipt.
    """
    products: List[ProductItem]
    payment: PaymentData


# =============================================================================
#                           Receipt Responses
# =============================================================================

class ReceiptResponse(BaseModel):
    """
    Detailed information about a receipt.

    Attributes:
        id (UUID): Unique identifier of the receipt.
        products (List[CalculatedProduct]): List of products with calculated totals.
        payment (PaymentData): Payment info for this receipt.
        total (Decimal): Total amount for the receipt.
        rest (Decimal): Remaining balance after payment.
        created_at (datetime): Timestamp when the receipt was created.
    """
    id: UUID
    products: List[CalculatedProduct]
    payment: PaymentData
    total: Decimal
    rest: Decimal
    created_at: datetime


class ReceiptListResponse(BaseModel):
    """
    Response containing a list of receipts, typically for pagination or batch retrieval.

    Attributes:
        receipts (List[ReceiptResponse]): The list of receipts.
        total (int): The total count of receipts.
    """
    receipts: List[ReceiptResponse]
    total: int


class ReceiptResponseOut(BaseModel):
    """
    Simplified response schema for a receipt, using a different product representation.

    Attributes:
        id (UUID): Unique identifier of the receipt.
        products (List[ReceiptItemResponse]): A list of items in the receipt.
        payment_type (str): Type of payment (e.g., 'cash', 'card').
        total (Decimal): The total amount for the receipt.
        paid_amount (Optional[Decimal]): The actual amount paid, if applicable.
        rest (Decimal): Remaining balance after payment.
        created_at (datetime): When the receipt was created.
    """
    id: UUID
    products: List[ReceiptItemResponse]
    payment_type: str
    total: Decimal
    paid_amount: Optional[Decimal]
    rest: Decimal
    created_at: datetime

    class Config:
        from_attributes = True
