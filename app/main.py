import os
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi_limiter import FastAPILimiter
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.connect import get_db
from app.router import auth, receipts
from app.service import messages
from app.service.config import config
from app.service.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage the application's lifespan events for startup and shutdown.

    This context manager initializes external resources (such as Redis and FastAPILimiter)
    during application startup and yields control to the application. Any exceptions during
    initialization are logged and re-raised.

    :param app: The FastAPI application instance.
    :type app: FastAPI
    :yields: None
    """
    logger.info("Starting up application and initializing Redis...")

    try:
        r = await redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            password=config.redis_password,
            db=0,
            encoding="utf-8",
            decode_responses=True,
        )
        await FastAPILimiter.init(r)
        logger.info("Redis initialization complete. FastAPILimiter is ready.")
    except Exception as exc:
        logger.exception("Unhandled exception during startup")
        raise exc

    yield  # Hand over control to the application


app = FastAPI(
    title="Test task",
    version="0.1.0",
    description="A FastAPI application demonstrating auth and receipts endpoints.",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(receipts.router)

# STATIC_DIR = "/app/static"
# if not os.path.isdir(STATIC_DIR):
#     os.makedirs(STATIC_DIR, exist_ok=True)
#
# app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health/db")
async def check_db_connection(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """
    Check the database connection by executing a simple SQL query.

    :param db: The asynchronous database session dependency.
    :type db: AsyncSession
    :return: A dictionary containing the status of the database connection.
    :rtype: dict[str, str]
    :raises HTTPException: If the database cannot be reached or returns an unexpected result.
    """
    logger.info("Checking database connection health...")
    try:
        result = await db.execute(text("SELECT 1"))
        value = result.scalar()
        if value != 1:
            logger.error(messages.DB_INCORRECT_VALUE)
            raise Exception(messages.DB_INCORRECT_VALUE)
        logger.info("Database connection is OK.")
        return {"status": "Database connection is OK"}
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=messages.DB_CANNOT_CONNECT
        )


@app.get("/")
def read_root() -> dict[str, str]:
    """
    Root endpoint for testing service availability.

    :return: A dictionary with a greeting message.
    :rtype: dict[str, str]
    """
    logger.info("Root endpoint accessed.")
    return {"message": "This is a test task for Checkbox!"}
