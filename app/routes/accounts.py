from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.database import get_db
from app.core.auth import verify_token

router = APIRouter()


@router.get("/accounts")
def get_accounts(
    db: Session = Depends(get_db),
    user=Depends(verify_token)
):
    clerk_id = user["sub"]

    accounts_result = db.execute(
        text("""
            SELECT *
            FROM accounts
            WHERE user_id = :user_id
            ORDER BY created_at DESC
        """),
        {"user_id": clerk_id}
    )

    accounts = accounts_result.mappings().all()

    return accounts


@router.get("/accounts/{account_id}")
def get_account_by_id(
    account_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(verify_token)
):
    clerk_id = user["sub"]

    account_result = db.execute(
        text("""
            SELECT *
            FROM accounts
            WHERE id = :account_id
              AND user_id = :user_id
            LIMIT 1
        """),
        {
            "account_id": str(account_id),
            "user_id": clerk_id
        }
    )

    account_row = account_result.mappings().first()

    if not account_row:
        raise HTTPException(
            status_code=404,
            detail="Account not found"
        )
    
    dividends_result = db.execute(
        text("""
            SELECT *
            FROM dividends
            WHERE account_id = :account_id
        """),
        {"account_id": str(account_id)}
    )

    positions_result = db.execute(
        text("""
            SELECT *
            FROM positions
            WHERE account_id = :account_id
        """),
        {"account_id": str(account_id)}
    )

    transactions_result = db.execute(
        text("""
            SELECT *
            FROM transactions
            WHERE account_id = :account_id
        """),
        {"account_id": str(account_id)}
    )

    account = {
        **dict(account_row),
        "dividends": dividends_result.mappings().all(),
        "positions": positions_result.mappings().all(),
        "transactions": transactions_result.mappings().all(),
    }

    return account


'''

Comando para testear:

curl -X GET http://localhost:8000/accounts/11833de7-4d95-4e97-a8f0-4615df01fccd -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsImNhdCI6ImNsX0I3ZDRQRDExMUFBQSIsImtpZCI6Imluc18zQ1VXOWx6QVQyUGtTbXVnRWxiZ2E4bnFnQjAiLCJvaWF0IjoxNzc5MjMwODE3LCJ0eXAiOiJKV1QifQ.eyJhenAiOiJodHRwczovL29ic2lkaWFuLXBvcnRhZm9saW8tZnJvbnRlbmQudmVyY2VsLmFwcCIsImV4cCI6MTc3OTIzMDg3NywiZnZhIjpbMzgsLTFdLCJpYXQiOjE3NzkyMzA4MTcsImlzcyI6Imh0dHBzOi8vd29ydGh5LWphY2thbC04MC5jbGVyay5hY2NvdW50cy5kZXYiLCJuYmYiOjE3NzkyMzA4MDcsInNpZCI6InNlc3NfM0R4ZkNHSXBmdnVvZHljYTVxVGZ5NDdUeFVmIiwic3RzIjoiYWN0aXZlIiwic3ViIjoidXNlcl8zRFFEaE1TYkpsQTdaaVR5S1hYeGxRaGpjMDgiLCJ2IjoyfQ.VuvqVL3qenUZLGTMuH99VAQYh6yLcZnYYb_7RZ11QvIQkr3TNGsSCPDgkOwpL38buoT0LHohm4deFWW-YlnjKcE6bPcdxvjirycYzTct6K6NJ8CYPub1IZNpKHCRjBGxalUPrrz2AQxtsi6XEQEj8fiNDJ0Mgz3U84EPL0uj54FTI45qFKLnfTCaPWSfloRRbLI4q97Qp1wAIEBv1VzI1ZwoJJFj3r53c0S1EWtATgp0rfr9LkxpftvAO0M19zbvXfG8EAuxc4dMH8REweonDFQBEWYxiDwaMp50zzi3V_PC45PVr3bWge0lSCyYp6giTRW1uxDc2kaGMyYhNVBauA"

'''