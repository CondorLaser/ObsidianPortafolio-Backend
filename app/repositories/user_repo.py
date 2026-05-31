from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Profile, RiskProfile


async def get_or_create_by_clerk_id(
    session: AsyncSession,
    clerk_id: str,
    email: str | None = None,
) -> Profile:
    stmt = (
        insert(Profile)
        .values(clerk_id=clerk_id, email=email)
        .on_conflict_do_nothing(index_elements=["clerk_id"])
    )
    await session.execute(stmt)
    await session.commit()

    result = await session.execute(
        select(Profile).where(Profile.clerk_id == clerk_id)
    )
    return result.scalar_one()


async def update_risk_profile(
    session: AsyncSession,
    user: Profile,
    risk_profile: RiskProfile,
) -> Profile:
    user.risk_profile = risk_profile
    await session.commit()
    await session.refresh(user)
    return user


async def upsert_from_clerk(
    session: AsyncSession,
    clerk_id: str,
    email: str | None,
) -> Profile:
    """Idempotente para webhooks: refresca el email si el user ya existía."""
    stmt = (
        insert(Profile)
        .values(clerk_id=clerk_id, email=email)
        .on_conflict_do_update(
            index_elements=["clerk_id"],
            set_={"email": email},
        )
    )
    await session.execute(stmt)
    await session.commit()
    result = await session.execute(
        select(Profile).where(Profile.clerk_id == clerk_id)
    )
    return result.scalar_one()


async def delete_by_clerk_id(session: AsyncSession, clerk_id: str) -> None:
    await session.execute(delete(Profile).where(Profile.clerk_id == clerk_id))
    await session.commit()
