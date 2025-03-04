from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import User
from app.service.schemas import UserSchema


async def get_user_by_login(login: str, db: AsyncSession) -> Optional[User]:
    """
    Retrieve a user from the database by login, in a case-insensitive manner.

    :param login: The user's login or username.
    :type login: str
    :param db: The async database session dependency.
    :type db: AsyncSession
    :return: The user object if found, otherwise None.
    :rtype: Optional[User]
    """
    sq = select(User).filter(func.lower(User.login) == func.lower(login))
    result = await db.execute(sq)
    user = result.scalar_one_or_none()
    return user


async def create_user(body: UserSchema, db: AsyncSession) -> User:
    """
    Create a new user in the database based on the provided schema data.

    :param body: The data required to create a new user, including fields like login and password.
    :type body: UserSchema
    :param db: The async database session dependency.
    :type db: AsyncSession
    :return: The newly created user object with a database-generated ID.
    :rtype: User
    """
    new_user = User(**body.model_dump())
    db.add(new_user)

    await db.commit()
    await db.refresh(new_user)
    return new_user


async def update_token(user: User, token: str | None, db: AsyncSession) -> None:
    """
    Update the user's refresh token in the database.

    :param user: The user whose refresh token needs to be updated.
    :type user: User
    :param token: The new refresh token, or None to clear it.
    :type token: str | None
    :param db: The async database session dependency.
    :type db: AsyncSession
    :return: None
    :rtype: None
    """
    user.refresh_token = token
    await db.commit()
