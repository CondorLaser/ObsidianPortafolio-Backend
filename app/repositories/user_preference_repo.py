from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_preference import UserPreference
from app.schemas.user_preference import UserPreferenceUpdate


async def get_for_user(
    session: AsyncSession, clerk_id: str
) -> UserPreference | None:
    result = await session.execute(
        select(UserPreference).where(UserPreference.user_id == clerk_id)
    )
    return result.scalar_one_or_none()


async def upsert_for_user(
    session: AsyncSession,
    clerk_id: str,
    payload: UserPreferenceUpdate,
) -> UserPreference:
    """Upsert: crea si no existe, actualiza solo los campos provistos si existe."""
    existing = await get_for_user(session, clerk_id)
    fields = payload.model_dump(exclude_unset=True)

    if existing is None:
        pref = UserPreference(user_id=clerk_id, **fields)
        session.add(pref)
    else:
        for k, v in fields.items():
            setattr(existing, k, v)
        pref = existing

    await session.commit()
    await session.refresh(pref)
    return pref
