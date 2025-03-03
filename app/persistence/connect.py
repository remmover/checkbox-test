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

    Attributes:
        _engine (AsyncEngine | None): The SQLAlchemy engine for async operations.
        _session_maker (async_sessionmaker | None): A session factory bound to the async engine.
    """

    def __init__(self, url: str):
        """
        Initialize the DatabaseSessionManager with a given database URL.

        Args:
            url (str): The database connection URL in the format:
                       'postgresql+asyncpg://user:password@host:port/db_name'.
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

        Yields:
            AsyncSession: The active database session within the context manager.

        Raises:
            Exception: If the session maker is not initialized.
            Exception: Reraises any exceptions encountered during the session block.
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

    Yields:
        AsyncSession: An active database session.

    Raises:
        Exception: Propagates any exceptions thrown inside the session context manager.
    """
    async with sessionmanager.session() as session:
        yield session
