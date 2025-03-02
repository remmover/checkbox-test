from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    status,
    Security,
)
from fastapi.security import (
    OAuth2PasswordRequestForm,
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.connect import get_db
from app.persistence.repository.auth import get_user_by_login, create_user, update_token
from app.service import messages
from app.service.auth import auth_service
from app.service.shemas import UserResponseSchema, UserSchema, TokenModel

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer()


@router.post(
    "/signup", response_model=UserResponseSchema, status_code=status.HTTP_201_CREATED
)
async def signup(
    body: UserSchema,
    db: AsyncSession = Depends(get_db),
):
    exist_user = await get_user_by_login(body.login, db)
    if exist_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=messages.ACCOUNT_EXIST
        )
    body.password = auth_service.get_password_hash(body.password)
    new_user = await create_user(body, db)
    return new_user


@router.post("/login", response_model=TokenModel)
async def login(
    body: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)
):
    user = await get_user_by_login(body.username, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=messages.INVALID_LOGIN
        )
    if not auth_service.verify_password(body.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=messages.BAD_PASSWORD
        )
    access_token = await auth_service.create_access_token(data={"sub": user.login})
    refresh_token = await auth_service.create_refresh_token(data={"sub": user.login})
    await update_token(user, refresh_token, db)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.get("/refresh_token", response_model=TokenModel)
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db),
):
    token = credentials.credentials
    login = await auth_service.decode_refresh_token(token)
    user = await get_user_by_login(login, db)
    if user.refresh_token != token:
        await update_token(user, None, db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=messages.BAD_REFRESH_TOKEN
        )

    access_token = await auth_service.create_access_token(data={"sub": login})
    refresh_token = await auth_service.create_refresh_token(data={"sub": login})
    await update_token(user, refresh_token, db)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }
