from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app.db.database import get_db
from app.db.models import User
from app.schemas import (
    UserResponse
)
from app.core.auth import verify_token

router = APIRouter()


@router.get("/profile")
def get_profile(db: Session = Depends(get_db), user=Depends(verify_token)):
    clerk_id = user["sub"]

    print("👤 CLERK ID FROM TOKEN:", clerk_id)

    user_db = db.query(User).filter(User.clerk_id == clerk_id).first()

    print("🧾 USER FROM DB:", user_db)

    if not user_db:
        raise HTTPException(status_code=404, detail="User not found")

    return user_db

'''
curl -X GET http://localhost:8000/profile -H "Authorization: Bearer token"
'''