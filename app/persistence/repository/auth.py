from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import User
from app.service.shemas import UserSchema


async def get_user_by_login(login: str, db: AsyncSession) -> Optional[User]:
    """
    Retrieve a user from the database by login, in a case-insensitive manner.

    Args:
        login (str): The user's login or username.
        db (AsyncSession): The async database session dependency.

    Returns:
        Optional[User]: The user object if found, otherwise None.
    """

    sq = select(User).filter(func.lower(User.login) == func.lower(login))
    result = await db.execute(sq)
    user = result.scalar_one_or_none()
    return user


async def create_user(body: UserSchema, db: AsyncSession) -> User:
    """
    Create a new user in the database based on the provided schema data.

    Args:
        body (UserSchema): The data required to create a new user, including fields like login and password.
        db (AsyncSession): The async database session dependency.

    Returns:
        User: The newly created user object with a database-generated ID.
    """
    new_user = User(**body.model_dump())
    db.add(new_user)

    await db.commit()
    await db.refresh(new_user)
    return new_user


async def update_token(user: User, token: str | None, db: AsyncSession) -> None:
    """
    Update the user's refresh token in the database.

    Args:
        user (User): The user whose refresh token needs to be updated.
        token (str | None): The new refresh token, or None to clear it.
        db (AsyncSession): The async database session dependency.

    Returns:
        None
    """
    user.refresh_token = token
    await db.commit()
