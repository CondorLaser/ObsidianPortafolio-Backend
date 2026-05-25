from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import RiskProfile, User


async def get_or_create_by_clerk_id(
    session: AsyncSession,
    clerk_id: str,
    email: str | None = None,
) -> User:
    stmt = (
        insert(User)
        .values(clerk_id=clerk_id, email=email)
        .on_conflict_do_nothing(index_elements=["clerk_id"])
    )
    await session.execute(stmt)
    await session.commit()

    result = await session.execute(select(User).where(User.clerk_id == clerk_id))
    return result.scalar_one()


async def update_risk_profile(
    session: AsyncSession,
    user: User,
    risk_profile: RiskProfile,
) -> User:
    user.risk_profile = risk_profile
    await session.commit()
    await session.refresh(user)
    return user


async def upsert_from_clerk(
    session: AsyncSession,
    clerk_id: str,
    email: str | None,
) -> User:
    """Idempotente para webhooks: refresca el email si el user ya existía."""
    stmt = (
        insert(User)
        .values(clerk_id=clerk_id, email=email)
        .on_conflict_do_update(
            index_elements=["clerk_id"],
            set_={"email": email},
        )
    )
    await session.execute(stmt)
    await session.commit()
    result = await session.execute(select(User).where(User.clerk_id == clerk_id))
    return result.scalar_one()


async def delete_by_clerk_id(session: AsyncSession, clerk_id: str) -> None:
    await session.execute(delete(User).where(User.clerk_id == clerk_id))
    await session.commit()
