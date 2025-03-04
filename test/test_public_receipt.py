import os
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.router.receipts import public_receipt


@pytest.mark.asyncio
async def test_public_receipt_txt_file_success():
    mock_receipt_id = uuid4()
    mock_db = AsyncMock(spec=AsyncSession)

    with patch('app.router.receipts.prepare_receipt_files') as mock_prepare_files, \
        patch('app.router.receipts.FileResponse') as mock_file_response, \
        patch('os.path.isfile', return_value=True):
        mock_prepare_files.return_value = ('/path/to/text.txt', '/path/to/qr.png')

        response = await public_receipt(
            receipt_id=mock_receipt_id,
            file_type='txt',
            line_length=40,
            db=mock_db
        )

        mock_prepare_files.assert_called_once_with(mock_db, mock_receipt_id, 40)
        mock_file_response.assert_called_once_with(
            path='/path/to/text.txt',
            media_type='text/plain',
            headers={'Content-Disposition': f'inline; filename={os.path.basename("/path/to/text.txt")}'}
        )


@pytest.mark.asyncio
async def test_public_receipt_qr_file_success():
    mock_receipt_id = uuid4()
    mock_db = AsyncMock(spec=AsyncSession)

    with patch('app.router.receipts.prepare_receipt_files') as mock_prepare_files, \
        patch('app.router.receipts.FileResponse') as mock_file_response, \
        patch('os.path.isfile', return_value=True):
        mock_prepare_files.return_value = ('/path/to/text.txt', '/path/to/qr.png')

        response = await public_receipt(
            receipt_id=mock_receipt_id,
            file_type='qr',
            line_length=40,
            db=mock_db
        )

        mock_prepare_files.assert_called_once_with(mock_db, mock_receipt_id, 40)
        mock_file_response.assert_called_once_with(
            path='/path/to/qr.png',
            media_type='image/png',
            headers={'Content-Disposition': f'inline; filename={os.path.basename("/path/to/qr.png")}'}
        )
