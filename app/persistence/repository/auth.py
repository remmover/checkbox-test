from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import User
from app.service.shemas import UserSchema


async def get_user_by_login(login: str, db: AsyncSession) -> User:
    sq = select(User).filter(func.lower(User.login) == func.lower(login))
    result = await db.execute(sq)
    user = result.scalar_one_or_none()
    return user


async def create_user(body: UserSchema, db: AsyncSession) -> User:
    new_user = User(**body.model_dump())
    db.add(new_user)

    await db.commit()
    await db.refresh(new_user)
    return new_user


async def update_token(user: User, token: str | None, db: AsyncSession) -> None:
    user.refresh_token = token
    await db.commit()


async def update_user_password(
    user: User, hashed_password: str, db: AsyncSession
) -> None:
    user.password = hashed_password
    await db.commit()
