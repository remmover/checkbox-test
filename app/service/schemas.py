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

    :ivar name: The user's name (length between 5 and 16).
    :vartype name: str
    :ivar login: The user's username/login.
    :vartype login: str
    :ivar password: The user's password (length between 6 and 10).
    :vartype password: str
    """
    name: str = Field(min_length=5, max_length=16)
    login: str
    password: str = Field(min_length=6, max_length=10)


class UserResponseSchema(BaseModel):
    """
    Response schema with basic user information.

    :ivar id: The unique identifier of the user.
    :vartype id: UUID
    :ivar login: The user's username/login.
    :vartype login: str
    """
    id: UUID
    login: str

    model_config = ConfigDict(from_attributes=True)


class TokenModel(BaseModel):
    """
    Model containing authentication tokens.

    :ivar access_token: The access token string.
    :vartype access_token: str
    :ivar refresh_token: The refresh token string.
    :vartype refresh_token: str
    :ivar token_type: The token type, defaults to 'bearer'.
    :vartype token_type: str
    """
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# =============================================================================
#                             Products
# =============================================================================

class ProductBase(BaseModel):
    """
    Base model describing a product to avoid duplication.

    :ivar name: The name of the product.
    :vartype name: str
    :ivar price: The price of the product.
    :vartype price: Decimal
    :ivar quantity: The quantity of the product.
    :vartype quantity: int
    """
    name: str
    price: Decimal
    quantity: int


class ProductItem(ProductBase):
    """
    A product item inherited from ProductBase, kept for backward compatibility
    or for further extension.
    """
    # Inherits name, price, quantity directly from ProductBase
    pass


class CalculatedProduct(ProductBase):
    """
    A product with a computed 'total' field (price * quantity).

    :ivar total: The computed total for the product.
    :vartype total: Decimal
    """
    total: Decimal


class ReceiptItemResponse(BaseModel):
    """
    Simplified model for displaying an item within a receipt, using different field
    names from the base product for clarity.

    :ivar product_name: The name of the product.
    :vartype product_name: str
    :ivar unit_price: The unit price of the product.
    :vartype unit_price: Decimal
    :ivar quantity: The quantity of the product purchased.
    :vartype quantity: int
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

    :ivar type: The type of payment; must be either 'cash' or 'card'.
    :vartype type: str
    :ivar amount: The payment amount; required if the payment type is 'cash'.
    :vartype amount: Optional[Decimal]
    """
    type: str
    amount: Optional[Decimal] = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        """
        Validates the payment type to ensure it is either 'cash' or 'card'.

        :param v: The payment type value.
        :type v: str
        :raises ValueError: If the payment type is invalid.
        :return: The validated payment type.
        :rtype: str
        """
        logger.debug("Validating payment type: %s", v)
        if v not in ("cash", "card"):
            logger.error(messages.INVALID_PAYMENT_TYPE)
            raise ValueError(messages.INVALID_PAYMENT_TYPE)
        return v

    @model_validator(mode="after")
    def check_cash_amount(self):
        """
        Validates that an amount is provided when the payment type is 'cash'.

        :raises ValueError: If payment type is 'cash' but `amount` is None.
        :return: The validated PaymentData instance.
        :rtype: PaymentData
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

    :ivar products: List of product items included in the receipt.
    :vartype products: List[ProductItem]
    :ivar payment: Payment information for this receipt.
    :vartype payment: PaymentData
    """
    products: List[ProductItem]
    payment: PaymentData


# =============================================================================
#                           Receipt Responses
# =============================================================================

class ReceiptResponse(BaseModel):
    """
    Detailed information about a receipt.

    :ivar id: Unique identifier of the receipt.
    :vartype id: UUID
    :ivar products: List of products with calculated totals.
    :vartype products: List[CalculatedProduct]
    :ivar payment: Payment information for this receipt.
    :vartype payment: PaymentData
    :ivar total: Total amount for the receipt.
    :vartype total: Decimal
    :ivar rest: Remaining balance after payment.
    :vartype rest: Decimal
    :ivar created_at: Timestamp when the receipt was created.
    :vartype created_at: datetime
    """
    id: UUID
    products: List[CalculatedProduct]
    payment: PaymentData
    total: Decimal
    rest: Decimal
    created_at: datetime


class ReceiptListResponse(BaseModel):
    """
    Response containing a list of receipts, typically used for pagination or batch retrieval.

    :ivar receipts: The list of receipt details.
    :vartype receipts: List[ReceiptResponse]
    :ivar total: The total count of receipts.
    :vartype total: int
    """
    receipts: List[ReceiptResponse]
    total: int


class ReceiptResponseOut(BaseModel):
    """
    Simplified response schema for a receipt, utilizing a different product representation.

    :ivar id: Unique identifier of the receipt.
    :vartype id: UUID
    :ivar products: A list of items in the receipt.
    :vartype products: List[ReceiptItemResponse]
    :ivar payment_type: Type of payment (e.g., 'cash', 'card').
    :vartype payment_type: str
    :ivar total: Total amount for the receipt.
    :vartype total: Decimal
    :ivar paid_amount: The actual amount paid, if applicable.
    :vartype paid_amount: Optional[Decimal]
    :ivar rest: Remaining balance after payment.
    :vartype rest: Decimal
    :ivar created_at: Timestamp when the receipt was created.
    :vartype created_at: datetime
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
