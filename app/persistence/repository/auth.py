from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import User
from app.service.shemas import UserSchema


async def get_user_by_login(login: str, db: AsyncSession) -> User:
    """
    Retrieves an user with the unique specific login.
    Email is searched in case-insensitive way. For example, emails
    hero@example.com, Hero@example.com, HERO@EXAMPLE.COM, etc.,
    are the same.

    :param login: The login to retrieve user for.
    :type login: str
    :param db: The database session.
    :type db: Session
    :return: An user which is identified by login.
    :rtype: User
    """
    sq = select(User).filter(func.lower(User.login) == func.lower(login))
    result = await db.execute(sq)
    user = result.scalar_one_or_none()
    return user


async def create_user(body: UserSchema, db: AsyncSession) -> User:
    """
    Create a new user.

    :param body: UserSchema object containing user information.
    :param db: AsyncSession instance for database operations.
    :return: The newly created user object.
    """

    new_user = User(**body.model_dump())
    db.add(new_user)

    # num_users = await db.execute(select(func.count(User.id)))
    # num_users = num_users.scalar()

    await db.commit()
    await db.refresh(new_user)
    return new_user


async def update_token(user: User, token: str | None, db: AsyncSession) -> None:
    """
    Update the refresh token for a user.

    :param user: User object for whom to update the token.
    :param token: New refresh token value or None.
    :param db: AsyncSession instance for database operations.
    """
    user.refresh_token = token
    await db.commit()


async def update_user_password(
    user: User, hashed_password: str, db: AsyncSession
) -> None:
    """
    Update a user's password.

    :param user: User object to update.
    :param hashed_password: New hashed password value.
    :param db: AsyncSession instance for database operations.
    """
    user.password = hashed_password
    await db.commit()
