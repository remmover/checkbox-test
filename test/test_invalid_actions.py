from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.main import app
from app.persistence.connect import get_db
from app.router.receipts import public_receipt, get_receipt, create_receipt
from app.service.schemas import PaymentData, ProductItem, ReceiptCreateSchema
from app.service.utils import prepare_receipt_files


def override_get_db():
    yield None


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


def test_login_invalid_login(client):
    login_data = {"username": "nonexistent", "password": "secretP"}
    response = client.post("/auth/login", data=login_data)
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data


def test_login_invalid_password(client):
    user_data = {
        "name": "TestUser",
        "login": "testlogin",
        "password": "secretP"
    }
    client.post("/auth/signup", json=user_data)
    login_data = {"username": "testlogin", "password": "wrongPassword"}
    response = client.post("/auth/login", data=login_data)
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data


def test_refresh_token_invalid_token(client):
    user_data = {
        "name": "TestUser",
        "login": "testlogin",
        "password": "secretP"
    }
    client.post("/auth/signup", json=user_data)
    login_data = {"username": "testlogin", "password": "secretP"}
    login_resp = client.post("/auth/login", data=login_data)
    token_data = login_resp.json()
    valid_refresh_token = token_data["refresh_token"]

    invalid_token = valid_refresh_token + "invalid"
    response = client.get(
        "/auth/refresh_token", headers={"Authorization": f"Bearer {invalid_token}"}
    )
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data


def test_download_receipt_file_invalid_file_type():
    receipt_id = str(uuid4())
    params = {"file_type": "invalid", "line_length": 40}
    response = client.get(f"/receipt/public/{receipt_id}/view", params=params)
    assert response.status_code == 400, response.text
    data = response.json()
    assert "detail" in data


def test_download_receipt_file_not_found(monkeypatch):
    async def fake_prepare_receipt_files(db, receipt_id, line_length):
        return "nonexistent.txt", "nonexistent_qr.png"

    monkeypatch.setattr(prepare_receipt_files, "__call__", fake_prepare_receipt_files)

    receipt_id = str(uuid4())
    params = {"file_type": "txt", "line_length": 40}
    response = client.get(f"/receipt/public/{receipt_id}/view", params=params)
    assert response.status_code == 500, response.text
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_public_receipt_file_not_found():
    mock_receipt_id = uuid4()
    mock_db = AsyncMock(spec=AsyncSession)

    with patch('app.router.receipts.prepare_receipt_files') as mock_prepare_files, \
        patch('os.path.isfile', return_value=False):
        mock_prepare_files.return_value = ('/path/to/text.txt', '/path/to/qr.png')

        with pytest.raises(HTTPException) as exc_info:
            await public_receipt(
                receipt_id=mock_receipt_id,
                file_type='txt',
                line_length=40,
                db=mock_db
            )

        assert exc_info.value.status_code == 404
        assert 'TXT file not found on server' in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_public_receipt_invalid_file_type():
    mock_receipt_id = uuid4()
    mock_db = AsyncMock(spec=AsyncSession)

    with pytest.raises(HTTPException) as exc_info:
        await public_receipt(
            receipt_id=mock_receipt_id,
            file_type='invalid',
            line_length=40,
            db=mock_db
        )

    assert exc_info.value.status_code == 400
    assert "file_type must be 'txt' or 'qr'" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_create_receipt_insufficient_cash():
    receipt_request = ReceiptCreateSchema(
        products=[
            ProductItem(name="Item1", price=Decimal("20.00"), quantity=2)
        ],
        payment=PaymentData(type="cash", amount=Decimal("30.00"))
    )

    mock_user = AsyncMock(id=1)
    mock_db = AsyncMock(spec=AsyncSession)

    with pytest.raises(HTTPException) as exc_info:
        await create_receipt(
            receipt_request,
            current_user=mock_user,
            db=mock_db
        )

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_create_receipt_invalid_payment_type():
    with pytest.raises(ValidationError) as exc_info:
        ReceiptCreateSchema(
            products=[
                ProductItem(name="Item1", price=Decimal("10.00"), quantity=1)
            ],
            payment=PaymentData(type="bank_transfer")
        )

    error = exc_info.value
    assert len(error.errors()) == 1
    assert error.errors()[0]['type'] == 'value_error'
    assert 'Invalid payment type' in error.errors()[0]['msg']


@pytest.mark.asyncio
async def test_get_receipt_by_id_not_found():
    receipt_id = uuid4()
    mock_user = AsyncMock(id=1)
    mock_db = AsyncMock(spec=AsyncSession)

    with patch('app.router.receipts.fetch_receipt_by_id') as mock_fetch_receipt:
        mock_fetch_receipt.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await get_receipt(
                receipt_id=receipt_id,
                current_user=mock_user,
                db=mock_db
            )

        assert exc_info.value.status_code == 404
        assert "Receipt not found" in str(exc_info.value.detail)
