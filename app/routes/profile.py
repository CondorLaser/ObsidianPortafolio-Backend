from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text

from app.db.database import get_db
from app.schemas import ProfileResponse, DividendResponse, TransactionResponse
from app.core.auth import verify_token

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileResponse)
def get_profile(
    db: Session = Depends(get_db),
    user=Depends(verify_token)
):
    clerk_id = user["sub"]
    print("👤 CLERK ID FROM TOKEN:", clerk_id)

    result = db.execute(
        text("""
            SELECT *
            FROM profiles
            WHERE clerk_id = :clerk_id
            LIMIT 1
        """),
        {"clerk_id": clerk_id}
    )

    profile = result.mappings().first()

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return dict(profile)

'''
@router.get("/dividends")
def get_dividends(
    db: Session = Depends(get_db),
    user_token=Depends(verify_token)
):
    clerk_id = user_token["sub"]

    user = get_user_from_clerk(db, clerk_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return (
        db.query(Dividend)
        .filter(Dividend.account_id == user.id)
        .all()
    )

@router.get("/transactions")
def get_transactions(
    db: Session = Depends(get_db),
    user_token=Depends(verify_token)
):
    clerk_id = user_token["sub"]

    user = get_user_from_clerk(db, clerk_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    transactions = (
        db.query(Transaction)
        .filter(Transaction.account_id == user.id)
        .all()
    )

    return transactions
'''

'''

Comando para testear:

curl -X GET http://localhost:8000/profile -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsImNhdCI6ImNsX0I3ZDRQRDExMUFBQSIsImtpZCI6Imluc18zQ1VXOWx6QVQyUGtTbXVnRWxiZ2E4bnFnQjAiLCJvaWF0IjoxNzc5MjI4NjQ2LCJ0eXAiOiJKV1QifQ.eyJhenAiOiJodHRwczovL29ic2lkaWFuLXBvcnRhZm9saW8tZnJvbnRlbmQudmVyY2VsLmFwcCIsImV4cCI6MTc3OTIyODcwNiwiZnZhIjpbMiwtMV0sImlhdCI6MTc3OTIyODY0NiwiaXNzIjoiaHR0cHM6Ly93b3J0aHktamFja2FsLTgwLmNsZXJrLmFjY291bnRzLmRldiIsIm5iZiI6MTc3OTIyODYzNiwic2lkIjoic2Vzc18zRHhmQ0dJcGZ2dW9keWNhNXFUZnk0N1R4VWYiLCJzdHMiOiJhY3RpdmUiLCJzdWIiOiJ1c2VyXzNEUURoTVNiSmxBN1ppVHlLWFh4bFFoamMwOCIsInYiOjJ9.pyhWxkFCljn72F_HkKwW1dEPiHuDnSJgxR5w7Y8oyXhK9WakqAL_chA-IfB4RSu44pgX0enGiul8e8MQpGPAG85oKc0vKSt7-HA0oUGEx_JYXm8inqL3g0lV8b4vS6tgTa2kLdMhzvhpUdezzyYepYUctI1JYAH2z2gDmuv4xC0Cpa73upiOiM6svNUlCSZMSvBR8n91707yvRFJq9T7ReBVcQW0xifkUPEl7hYVbldvzpJzeKYxQUqYaC8Box0X7PNAIxltmlr0RyVfV2DCjQ9LHM-xnU0sD5dZR-brXADCcNQS5DWlBy2kRxfW-aw1_2Fu-wqeQOsqoGriFYHUGw"

'''