import pytest
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
import fastapi_limiter

from app.main import app
from app.persistence.connect import get_db
from app.persistence.models import Base

TEST_SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./test.db"
engine = create_async_engine(TEST_SQLALCHEMY_DATABASE_URL, echo=False)
async_session = async_sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def mock_fastapi_limiter_init():
    original_init = fastapi_limiter.FastAPILimiter.init
    fastapi_limiter.FastAPILimiter.init = AsyncMock(return_value=None)
    yield
    fastapi_limiter.FastAPILimiter.init = original_init


@pytest.fixture
async def test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session


def override_get_db():
    try:
        db = async_session()
        yield db
    finally:
        db.close()


@pytest.fixture
def client(test_db):
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
