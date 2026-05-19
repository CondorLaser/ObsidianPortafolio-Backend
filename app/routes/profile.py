from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app.db.database import get_db
from app.db.models import User, Dividend, Transaction
from app.schemas import UserResponse, DividendResponse, TransactionResponse
from app.core.auth import verify_token

router = APIRouter(prefix="/profile", tags=["profile"])

def get_user_from_clerk(db: Session, clerk_id: str):
    user = db.query(User).filter(User.clerk_id == clerk_id).first()
    return user

@router.get("")
def get_profile(db: Session = Depends(get_db), user=Depends(verify_token)):
    clerk_id = user["sub"]

    print("👤 CLERK ID FROM TOKEN:", clerk_id)

    user_db = get_user_from_clerk(db, clerk_id)

    print("🧾 USER FROM DB:", user_db)

    if not user_db:
        raise HTTPException(status_code=404, detail="User not found")

    return user_db

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
Comando para testear:
curl -X GET http://localhost:8000/profile/transactions -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsImNhdCI6ImNsX0I3ZDRQRDExMUFBQSIsImtpZCI6Imluc18zQ1VXOWx6QVQyUGtTbXVnRWxiZ2E4bnFnQjAiLCJvaWF0IjoxNzc5MTUzMTM2LCJ0eXAiOiJKV1QifQ.eyJhenAiOiJodHRwczovL29ic2lkaWFuLXBvcnRhZm9saW8tZnJvbnRlbmQudmVyY2VsLmFwcCIsImV4cCI6MTc3OTE1MzE5NiwiZnZhIjpbNDQsLTFdLCJpYXQiOjE3NzkxNTMxMzYsImlzcyI6Imh0dHBzOi8vd29ydGh5LWphY2thbC04MC5jbGVyay5hY2NvdW50cy5kZXYiLCJuYmYiOjE3NzkxNTMxMjYsInNpZCI6InNlc3NfM0R2Nnl5NWpXTmVvZzdHS2NOcEhrN3I1VnBhIiwic3RzIjoiYWN0aXZlIiwic3ViIjoidXNlcl8zRHY2eXpueHZZSWV5cWVEN09XM2M4dEUxbzQiLCJ2IjoyfQ.GCK5UcQu1vptynN9_owQ1U-lBQCq1-g1hfWwXm6RUhadXeSAxOqMavtwqOMw2d2-bBDJNTTy59-oIYhiPbzJnG_9cODm190nG01zJ0MC-FgylnHdkhRPsfD_L30LLXeu1cjuOC3nVnbI7wXUIcsCdmfQXMpwP8XYSHtK1dg-rhO2b7_K4_5GTPI4mzwvmpH9YmzqY1E-Rcl5LxaLmrZnlhirxuGlcCvvzrAUCTuKqyze3YyNu8HZhUjPRlLZ0Y-iyn4hnXc-ZP9LtOq9MG6jBMw2-NeR1QoRSXPV2n8igTSaDPmqcJwKvfzSDe1CV4Y2cczEUMGY2uv561zEKWvPlg"
'''