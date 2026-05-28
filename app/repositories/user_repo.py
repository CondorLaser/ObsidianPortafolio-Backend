from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


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
    db: AsyncSession,
    user_id: str,
    risk_profile: str,
):
    result = await db.execute(
        select(User).where(User.clerk_id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="404 user not found")
    
    user.risk_profile = risk_profile
    await db.commit()
    await db.refresh(user)
    return user
