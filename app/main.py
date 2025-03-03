import logging
import os

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from starlette.middleware.cors import CORSMiddleware
from fastapi_limiter import FastAPILimiter
from fastapi.staticfiles import StaticFiles
import redis.asyncio as redis

from app.persistence.connect import get_db
from app.router import auth, receipts
from app.service.config import config

app = FastAPI(title="Test task", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(receipts.router)
STATIC_DIR = "/app/static"

if not os.path.isdir(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
async def startup():
    r = await redis.Redis(
        host=config.redis_host,
        port=config.redis_port,
        password=config.redis_password,
        db=0,
        encoding="utf-8",
        decode_responses=True,
    )
    await FastAPILimiter.init(r)


@app.get("/health/db")
async def check_db_connection(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(text("SELECT 1"))
        value = result.scalar()
        if value != 1:
            raise Exception("Incorrect value from the database")
        return {"status": "Database connection is OK"}
    except Exception as e:
        logging.exception(e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cannot connect to the database"
        )


@app.get("/")
def read_root():
    return {"message": "This is test task for Checkbox!"}
