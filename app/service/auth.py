import pickle
import datetime
from datetime import timedelta
from typing import Optional, Dict, Any

import redis
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.connect import get_db
from app.persistence.repository.auth import get_user_by_login
from app.service import messages
from app.service.config import config
from app.service.logger import logger


class Auth:
    """
    A service class handling authentication and token management,
    using timezone-aware datetimes in UTC.
    """
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    SECRET_KEY: str = config.secret_key
    ALGORITHM: str = config.algorithm
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
    cache = redis.Redis(
        host=config.redis_host,
        port=config.redis_port,
        password=config.redis_password,
        db=0,
    )

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verifies a plain text password against a hashed password."""
        logger.debug("Verifying password.")
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Hashes a plain text password using bcrypt."""
        logger.debug("Generating password hash.")
        return self.pwd_context.hash(password)

    async def create_access_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[float] = None
    ) -> str:
        """
        Creates an access token (JWT) with an optional expiration in seconds.
        Uses timezone-aware datetime.
        """
        logger.debug(f"Creating access token for data: {data}, expires in: {expires_delta} seconds.")
        to_encode = data.copy()

        now_utc = datetime.datetime.now(datetime.UTC)
        if expires_delta:
            expire = now_utc + timedelta(seconds=expires_delta)
        else:
            expire = now_utc + timedelta(minutes=60)

        to_encode.update({
            "iat": now_utc,
            "exp": expire,
            "scope": "access_token",
        })

        encoded_access_token = jwt.encode(
            to_encode,
            self.SECRET_KEY,
            algorithm=self.ALGORITHM
        )
        return encoded_access_token

    async def create_refresh_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[float] = None
    ) -> str:
        """
        Creates a refresh token (JWT) with an optional expiration in seconds.
        Uses timezone-aware datetime.
        """
        logger.debug(f"Creating refresh token for data: {data}, expires in: {expires_delta} seconds.")
        to_encode = data.copy()

        now_utc = datetime.datetime.now(datetime.UTC)
        if expires_delta:
            expire = now_utc + timedelta(seconds=expires_delta)
        else:
            expire = now_utc + timedelta(days=7)

        to_encode.update({
            "iat": now_utc,
            "exp": expire,
            "scope": "refresh_token",
        })

        encoded_refresh_token = jwt.encode(
            to_encode,
            self.SECRET_KEY,
            algorithm=self.ALGORITHM
        )
        return encoded_refresh_token

    async def get_login_from_token(self, token: str) -> str:
        """
        Extracts the 'sub' (login) from an access or refresh token.
        Raises HTTPException if the token is invalid.
        """
        logger.debug("Decoding token to get login (sub).")
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            return payload["sub"]
        except JWTError as e:
            logger.exception("Error decoding token to extract login.")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=messages.INVALID_SCOPE_TOKEN,
            ) from e

    async def decode_refresh_token(self, refresh_token: str) -> str:
        """
        Validates a refresh token and returns the 'sub' (login) if valid.
        Raises HTTPException if the token is invalid or not a refresh token.
        """
        logger.debug("Decoding and validating refresh token.")
        try:
            payload = jwt.decode(refresh_token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            if payload.get("scope") == "refresh_token":
                return payload["sub"]
            logger.error("Token scope is not refresh_token.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=messages.INVALID_SCOPE_TOKEN,
            )
        except JWTError:
            logger.exception("Refresh token is invalid or expired.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=messages.VALIDATE_CREDENTIALS,
            )

    async def get_current_user(
        self,
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db)
    ) -> Any:
        """
        Retrieves the current user from the access token or raises an exception if invalid.
        """
        logger.debug("Retrieving current user from token.")
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=messages.VALIDATE_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )

        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            if payload.get("scope") != "access_token":
                logger.error("Token scope is not 'access_token'.")
                raise credentials_exception

            login = payload.get("sub")
            if not login:
                logger.error("No 'sub' found in token payload.")
                raise credentials_exception
        except JWTError:
            logger.exception("Error decoding or validating token.")
            raise credentials_exception

        # Attempt to get user from Redis cache
        cached_user = self.cache.get(f"user:{login}")
        if cached_user is None:
            logger.debug(f"User not found in cache. Querying database for login: {login}.")
            user_db = await get_user_by_login(login, db)
            if user_db is None:
                logger.error("No user found in database with given login.")
                raise credentials_exception

            self.cache.set(f"user:{login}", pickle.dumps(user_db))
            self.cache.expire(f"user:{login}", 900)  # 15-minute cache expiration
            return user_db
        else:
            logger.debug("User found in cache. Deserializing data.")
            return pickle.loads(cached_user)


auth_service = Auth()
