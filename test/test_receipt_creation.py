import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID, uuid4

from app.service.schemas import ReceiptCreateSchema, ProductItem, PaymentData
from app.router.receipts import create_receipt


@pytest.mark.asyncio
async def test_create_receipt_cash_payment_success():
    receipt_request = ReceiptCreateSchema(
        products=[
            ProductItem(name="Item1", price=Decimal("10.00"), quantity=2),
            ProductItem(name="Item2", price=Decimal("15.50"), quantity=1)
        ],
        payment=PaymentData(type="cash", amount=Decimal("35.50"))
    )

    mock_user = AsyncMock(id=1)
    mock_db = AsyncMock(spec=AsyncSession)

    with patch('app.router.receipts.create_receipt_in_db') as mock_create_receipt:
        mock_receipt = AsyncMock(
            id=uuid4(),
            total_amount=Decimal("35.50"),
            created_at="2024-03-04T12:00:00"
        )
        mock_create_receipt.return_value = mock_receipt

        response = await create_receipt(
            receipt_request,
            current_user=mock_user,
            db=mock_db
        )

        assert isinstance(response.id, UUID)
        assert response.total == Decimal("35.50")
        assert response.rest == Decimal("0.00")
        assert len(response.products) == 2
        assert response.payment.type == "cash"


@pytest.mark.asyncio
async def test_create_receipt_card_payment():
    receipt_request = ReceiptCreateSchema(
        products=[
            ProductItem(name="Item1", price=Decimal("25.00"), quantity=1)
        ],
        payment=PaymentData(type="card")
    )

    mock_user = AsyncMock(id=1)
    mock_db = AsyncMock(spec=AsyncSession)

    with patch('app.router.receipts.create_receipt_in_db') as mock_create_receipt:
        mock_receipt = AsyncMock(
            id=uuid4(),
            total_amount=Decimal("25.00"),
            created_at="2024-03-04T12:00:00"
        )
        mock_create_receipt.return_value = mock_receipt

        response = await create_receipt(
            receipt_request,
            current_user=mock_user,
            db=mock_db
        )

        assert isinstance(response.id, UUID)
        assert response.total == Decimal("25.00")
        assert response.rest == Decimal("0.00")
        assert response.payment.type == "card"


def test_payment_data_validation():
    valid_cash_payment = PaymentData(type="cash", amount=Decimal("50.00"))
    assert valid_cash_payment.type == "cash"

    valid_card_payment = PaymentData(type="card")
    assert valid_card_payment.type == "card"

    with pytest.raises(ValueError):
        PaymentData(type="bank_transfer")

    with pytest.raises(ValueError):
        PaymentData(type="cash")
