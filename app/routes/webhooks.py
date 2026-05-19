from fastapi import APIRouter, Request, HTTPException
from svix.webhooks import Webhook
from dotenv import load_dotenv

import psycopg2
import os
import json

load_dotenv()

router = APIRouter()

CLERK_WEBHOOK_SECRET = os.getenv("CLERK_WEBHOOK_SECRET")
DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)

@router.post("/webhooks/clerk")
async def clerk_webhook(request: Request):
    payload = await request.body()
    headers = request.headers
    
    svix_id = headers.get("svix-id")
    svix_timestamp = headers.get("svix-timestamp")
    svix_signature = headers.get("svix-signature")

    if not svix_id or not svix_timestamp or not svix_signature:
        raise HTTPException(status_code=400, detail="Missing svix headers")
    
    wh = Webhook(CLERK_WEBHOOK_SECRET)

    try:
        event = wh.verify(
            payload,
            {
                "svix-id": svix_id,
                "svix-timestamp": svix_timestamp,
                "svix-signature": svix_signature,
            },
        )
    
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    
    event_type = event["type"]
    if event_type == "user.created":
        data = event["data"]
        clerk_id = data["id"]
        email = data["email_addresses"][0]["email_address"]
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO "profiles" (clerk_id, email)
            VALUES (%s, %s)
            ON CONFLICT (clerk_id) DO NOTHING
            """,
            (clerk_id, email),
        )

        conn.commit()
        cur.close()

        print(f"Usuario creado: {email}")
    
    return {"status": "ok"}