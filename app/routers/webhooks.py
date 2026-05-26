from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from svix.webhooks import Webhook, WebhookVerificationError

from app.core.config import get_settings
from app.core.db import get_db
from app.repositories import user_repo

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _primary_email(data: dict) -> str | None:
    primary_id = data.get("primary_email_address_id")
    for addr in data.get("email_addresses") or []:
        if addr.get("id") == primary_id:
            return addr.get("email_address")
    addrs = data.get("email_addresses") or []
    return addrs[0].get("email_address") if addrs else None


@router.post("/clerk")
async def clerk_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    if not settings.CLERK_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CLERK_WEBHOOK_SECRET not configured",
        )

    svix_id = request.headers.get("svix-id")
    svix_timestamp = request.headers.get("svix-timestamp")
    svix_signature = request.headers.get("svix-signature")
    if not (svix_id and svix_timestamp and svix_signature):
        raise HTTPException(status_code=400, detail="Missing svix headers")

    payload = await request.body()
    try:
        event = Webhook(settings.CLERK_WEBHOOK_SECRET).verify(
            payload,
            {
                "svix-id": svix_id,
                "svix-timestamp": svix_timestamp,
                "svix-signature": svix_signature,
            },
        )
    except WebhookVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event_type = event.get("type")
    data = event.get("data") or {}
    clerk_id = data.get("id")
    if not clerk_id:
        raise HTTPException(status_code=400, detail="Missing user id in event")

    if event_type in ("user.created", "user.updated"):
        await user_repo.upsert_from_clerk(db, clerk_id, _primary_email(data))
    elif event_type == "user.deleted":
        await user_repo.delete_by_clerk_id(db, clerk_id)
    # otros tipos: ignorados con 200 (Clerk reintenta si != 2xx)

    return {"status": "ok"}  # response 1:1 con contrato Eduardo
