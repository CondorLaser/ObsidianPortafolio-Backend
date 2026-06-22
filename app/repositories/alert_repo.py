from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.schemas.alert import AlertUpdate


async def list_for_user(
    session: AsyncSession,
    clerk_id: str,
    skip: int = 0,
    limit: int = 100,
    is_read: bool | None = None,
    is_active: bool | None = None,
) -> list[Alert]:
    stmt = select(Alert).where(Alert.user_id == clerk_id)

    if is_read is not None:
        stmt = stmt.where(Alert.is_read == is_read)
    if is_active is not None:
        stmt = stmt.where(Alert.is_active == is_active)

    stmt = stmt.order_by(Alert.created_at.desc()).offset(skip).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_for_user(
    session: AsyncSession,
    clerk_id: str,
    alert_id: str,
    payload: AlertUpdate,
) -> Alert | None:
    stmt = select(Alert).where(Alert.id == alert_id, Alert.user_id == clerk_id)
    result = await session.execute(stmt)
    alert = result.scalar_one_or_none()
    if alert is None:
        return None

    if payload.is_read is not None:
        alert.is_read = payload.is_read
    if payload.is_active is not None:
        alert.is_active = payload.is_active

    await session.commit()
    await session.refresh(alert)
    return alert

async def count_for_user(
    session: AsyncSession,
    clerk_id: str,
) -> dict:
    base_stmt = select(Alert).where(Alert.user_id == clerk_id)
    
    # Contar leídas
    read_result = await session.execute(
        select(func.count()).select_from(Alert).where(
            Alert.user_id == clerk_id, Alert.is_read == True
        )
    )
    read_count = read_result.scalar() or 0
    
    # Contar no leídas
    unread_result = await session.execute(
        select(func.count()).select_from(Alert).where(
            Alert.user_id == clerk_id, Alert.is_read == False
        )
    )
    unread_count = unread_result.scalar() or 0
    
    # Contar activas
    active_result = await session.execute(
        select(func.count()).select_from(Alert).where(
            Alert.user_id == clerk_id, Alert.is_active == True
        )
    )
    active_count = active_result.scalar() or 0
    
    # Contar inactivas
    inactive_result = await session.execute(
        select(func.count()).select_from(Alert).where(
            Alert.user_id == clerk_id, Alert.is_active == False
        )
    )
    inactive_count = inactive_result.scalar() or 0
    
    return {
        "read": read_count,
        "unread": unread_count,
        "active": active_count,
        "inactive": inactive_count,
    }