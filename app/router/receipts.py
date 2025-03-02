from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.persistence.connect import get_db
from app.persistence.models import User
from app.service.auth import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/receipt", status_code=status.HTTP_200_OK)
async def create_receipt(data: dict, current_user: User = Depends(auth_service.get_current_user),
                         db: AsyncSession = Depends(get_db)):
    return {"message": "Receipt created successfully"}
