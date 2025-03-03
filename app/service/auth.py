import pickle
from typing import Optional

import redis
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.connect import get_db
from app.persistence.repository.auth import get_user_by_login
from app.service import messages
from app.service.config import config


class Auth:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    SECRET_KEY = config.secret_key
    ALGORITHM = config.algorithm
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
    cache = redis.Redis(
        host=config.redis_host,
        port=config.redis_port,
        password=config.redis_password,
        db=0,
    )

    def verify_password(self, plain_password, hashed_password):
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str):
        return self.pwd_context.hash(password)

    async def create_access_token(
        self, data: dict, expires_delta: Optional[float] = None
    ):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + timedelta(seconds=expires_delta)
        else:
            expire = datetime.utcnow() + timedelta(minutes=60)
        to_encode.update(
            {"iat": datetime.utcnow(), "exp": expire, "scope": "access_token"}
        )
        encoded_access_token = jwt.encode(
            to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM
        )
        return encoded_access_token

    async def create_refresh_token(
        self, data: dict, expires_delta: Optional[float] = None
    ):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + timedelta(seconds=expires_delta)
        else:
            expire = datetime.utcnow() + timedelta(days=7)
        to_encode.update(
            {"iat": datetime.utcnow(), "exp": expire, "scope": "refresh_token"}
        )
        encoded_refresh_token = jwt.encode(
            to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM
        )
        return encoded_refresh_token

    async def get_login_from_token(self, token: str):
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            login = payload["sub"]
            return login
        except JWTError as e:
            print(e)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=messages.INVALID_SCOPE_TOKEN,
            )

    async def decode_refresh_token(self, refresh_token: str):
        try:
            payload = jwt.decode(
                refresh_token, self.SECRET_KEY, algorithms=[self.ALGORITHM]
            )
            if payload["scope"] == "refresh_token":
                login = payload["sub"]
                return login
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=messages.INVALID_SCOPE_TOKEN,
            )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=messages.VALIDATE_CREDENTIALS,
            )

    async def get_current_user(
        self, token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
    ):
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=messages.VALIDATE_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )

        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            if payload["scope"] == "access_token":
                login = payload["sub"]
                if login is None:
                    raise credentials_exception
            else:
                raise credentials_exception
        except JWTError:
            raise credentials_exception

        user = self.cache.get(f"user:{login}")
        # user = None  # <-- cache is a reason why User.role is not changed quickly --!
        if user is None:
            user = await get_user_by_login(login, db)
            if user is None:
                raise credentials_exception
            self.cache.set(f"user:{login}", pickle.dumps(user))  # noqa
            self.cache.expire(f"user:{login}", 900)  # noqa
        else:
            user = pickle.loads(user)
        return user


auth_service = Auth()
