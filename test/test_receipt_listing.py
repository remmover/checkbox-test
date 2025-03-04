import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.service.schemas import ReceiptResponseOut
from app.persistence.models import Receipt, PaymentType
from app.router.receipts import list_receipts, get_receipt


@pytest.fixture
def mock_receipts():
    """
    Create a fixture with sample receipt data for testing.
    """
    now = datetime.now()
    receipts = [
        Receipt(
            id=uuid4(),
            user_id=uuid4(),
            payment_type=PaymentType.cash,
            total_amount=Decimal("50.00"),
            paid_amount=Decimal("60.00"),
            created_at=now - timedelta(days=5)
        ),
        Receipt(
            id=uuid4(),
            user_id=uuid4(),
            payment_type=PaymentType.card,
            total_amount=Decimal("75.50"),
            created_at=now - timedelta(days=2)
        )
    ]
    return receipts


@pytest.mark.asyncio
async def test_list_receipts_default_parameters():
    mock_user = AsyncMock(id=1)
    mock_db = AsyncMock(spec=AsyncSession)

    with patch('app.router.receipts.fetch_receipts') as mock_fetch_receipts, \
        patch('app.router.receipts.build_receipt_response_out') as mock_build_response:
        mock_receipts_data = [
            AsyncMock(
                id=uuid4(),
                total_amount=Decimal("50.00"),
                payment_type=PaymentType.cash,
                paid_amount=Decimal("50.00"),
                items=[],
                created_at=datetime.now()
            ),
            AsyncMock(
                id=uuid4(),
                total_amount=Decimal("75.50"),
                payment_type=PaymentType.card,
                paid_amount=None,
                items=[],
                created_at=datetime.now()
            )
        ]
        mock_fetch_receipts.return_value = mock_receipts_data

        mock_responses = [
            ReceiptResponseOut(
                id=receipt.id,
                products=[],
                payment_type=receipt.payment_type.value,
                total=receipt.total_amount,
                paid_amount=receipt.paid_amount,
                rest=Decimal("0.00"),
                created_at=receipt.created_at
            ) for receipt in mock_receipts_data
        ]
        mock_build_response.side_effect = mock_responses

        results = await list_receipts(
            current_user=mock_user,
            db=mock_db,
            start_date=None,
            end_date=None,
            min_total=None,
            payment_type=None,
            limit=10,
            offset=0
        )

        assert len(results) == 2
        assert all(isinstance(receipt, ReceiptResponseOut) for receipt in results)
        mock_fetch_receipts.assert_called_once_with(
            db=mock_db,
            user_id=1,
            start_date=None,
            end_date=None,
            min_total=None,
            payment_type=None,
            limit=10,
            offset=0
        )


@pytest.mark.asyncio
async def test_list_receipts_with_filters():
    start_date = datetime.now() - timedelta(days=7)
    end_date = datetime.now()

    mock_user = AsyncMock(id=1)
    mock_db = AsyncMock(spec=AsyncSession)

    with patch('app.router.receipts.fetch_receipts') as mock_fetch_receipts, \
        patch('app.router.receipts.build_receipt_response_out') as mock_build_response:
        mock_filtered_receipts = [
            AsyncMock(
                id=uuid4(),
                total_amount=Decimal("100.00"),
                payment_type=PaymentType.cash,
                paid_amount=Decimal("100.00"),
                items=[],
                created_at=datetime.now()
            )
        ]
        mock_fetch_receipts.return_value = mock_filtered_receipts

        mock_responses = [
            ReceiptResponseOut(
                id=receipt.id,
                products=[],
                payment_type=receipt.payment_type.value,
                total=receipt.total_amount,
                paid_amount=receipt.paid_amount,
                rest=Decimal("0.00"),
                created_at=receipt.created_at
            ) for receipt in mock_filtered_receipts
        ]
        mock_build_response.side_effect = mock_responses

        results = await list_receipts(
            start_date=start_date,
            end_date=end_date,
            min_total=Decimal("50.00"),
            payment_type="cash",
            limit=5,
            offset=0,
            current_user=mock_user,
            db=mock_db
        )

        assert len(results) == 1
        mock_fetch_receipts.assert_called_once_with(
            db=mock_db,
            user_id=1,
            start_date=start_date,
            end_date=end_date,
            min_total=Decimal("50.00"),
            payment_type="cash",
            limit=5,
            offset=0
        )


@pytest.mark.asyncio
async def test_get_receipt_by_id_success():
    receipt_id = uuid4()
    mock_user = AsyncMock(id=1)
    mock_db = AsyncMock(spec=AsyncSession)

    with patch('app.router.receipts.fetch_receipt_by_id') as mock_fetch_receipt:
        mock_receipt = AsyncMock(
            id=receipt_id,
            total_amount=Decimal("50.00"),
            payment_type=PaymentType.card
        )
        mock_fetch_receipt.return_value = mock_receipt

        result = await get_receipt(
            receipt_id=receipt_id,
            current_user=mock_user,
            db=mock_db
        )

        assert isinstance(result, ReceiptResponseOut)
        assert result.id == receipt_id
        mock_fetch_receipt.assert_called_once_with(
            db=mock_db,
            user_id=1,
            receipt_id=receipt_id
        )
