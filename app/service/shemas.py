from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, validator
from datetime import datetime


class UserSchema(BaseModel):
    name: str = Field(min_length=5, max_length=16)
    login: str
    password: str = Field(min_length=6, max_length=10)


class UserResponseSchema(BaseModel):
    id: UUID
    login: str
    model_config = ConfigDict(from_attributes=True)


class TokenModel(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ProductItem(BaseModel):
    name: str
    price: Decimal
    quantity: int


class PaymentData(BaseModel):
    type: str
    amount: Optional[Decimal] = None

    @validator('type')
    def validate_type(cls, v):
        if v not in ("cash", "card"):
            raise ValueError("Invalid payment type, must be 'cash' or 'card'")
        return v

    @validator('amount', always=True)
    def validate_amount(cls, v, values):
        if values.get('type') == "cash" and v is None:
            raise ValueError("Amount is required for cash payments")
        return v


class ReceiptCreateRequest(BaseModel):
    products: List[ProductItem]
    payment: PaymentData


class CalculatedProduct(ProductItem):
    total: Decimal


class ReceiptResponse(BaseModel):
    id: UUID
    products: List[CalculatedProduct]
    payment: PaymentData
    total: Decimal
    rest: Decimal
    created_at: datetime


class ReceiptListResponse(BaseModel):
    receipts: List[ReceiptResponse]
    total: int


class ReceiptItemResponse(BaseModel):
    product_name: str
    unit_price: Decimal
    quantity: int

    class Config:
        orm_mode = True
        from_attributes = True


class ReceiptResponseOut(BaseModel):
    id: UUID
    products: List[ReceiptItemResponse]
    payment_type: str
    total: Decimal
    paid_amount: Optional[Decimal]
    rest: Decimal
    created_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True
