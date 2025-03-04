import contextlib
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.service import messages
from app.service.config import config


class DatabaseSessionManager:
    """
    Manages the creation and usage of an asynchronous database session.

    :ivar _engine: The SQLAlchemy engine for async operations.
    :vartype _engine: AsyncEngine | None
    :ivar _session_maker: A session factory bound to the async engine.
    :vartype _session_maker: async_sessionmaker | None
    """

    def __init__(self, url: str):
        """
        Initialize the DatabaseSessionManager with a given database URL.

        :param url: The database connection URL in the format:
                    'postgresql+asyncpg://user:password@host:port/db_name'.
        :type url: str
        """
        self._engine: AsyncEngine | None = create_async_engine(url)
        self._session_maker: async_sessionmaker | None = async_sessionmaker(
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            bind=self._engine
        )

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """
        Provides an asynchronous context manager for database sessions.

        :yields: The active database session.
        :rtype: AsyncSession
        :raises Exception: If the session maker is not initialized or if any exception occurs during the session block.
        """
        if self._session_maker is None:
            raise Exception(messages.DB_CANNOT_CONNECT)
        session = self._session_maker()
        try:
            yield session
        except Exception as err:
            print(err)
            await session.rollback()
            raise
        finally:
            await session.close()


SQLALCHEMY_DATABASE_URL = (
    "postgresql+asyncpg://"
    + f"{config.postgres_user}:{config.postgres_password}"
    + f"@{config.postgres_host}:{config.postgres_port}"
    + f"/{config.postgres_db}"
)

sessionmanager = DatabaseSessionManager(SQLALCHEMY_DATABASE_URL)


async def get_db():
    """
    Dependency function that provides a database session for FastAPI endpoints.

    :yields: An active database session.
    :rtype: AsyncSession
    :raises Exception: Propagates any exceptions thrown inside the session context manager.
    """
    async with sessionmanager.session() as session:
        yield session
