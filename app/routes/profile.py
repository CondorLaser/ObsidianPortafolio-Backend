from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.database import get_db
from app.schemas import ProfileResponse
from app.core.auth import verify_token

router = APIRouter()


@router.get("/profile", response_model=ProfileResponse)
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

Comando para testear:

curl -X GET http://localhost:8000/profile -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsImNhdCI6ImNsX0I3ZDRQRDExMUFBQSIsImtpZCI6Imluc18zQ1VXOWx6QVQyUGtTbXVnRWxiZ2E4bnFnQjAiLCJvaWF0IjoxNzc5MjI5MjY0LCJ0eXAiOiJKV1QifQ.eyJhenAiOiJodHRwczovL29ic2lkaWFuLXBvcnRhZm9saW8tZnJvbnRlbmQudmVyY2VsLmFwcCIsImV4cCI6MTc3OTIyOTMyNCwiZnZhIjpbMTIsLTFdLCJpYXQiOjE3NzkyMjkyNjQsImlzcyI6Imh0dHBzOi8vd29ydGh5LWphY2thbC04MC5jbGVyay5hY2NvdW50cy5kZXYiLCJuYmYiOjE3NzkyMjkyNTQsInNpZCI6InNlc3NfM0R4ZkNHSXBmdnVvZHljYTVxVGZ5NDdUeFVmIiwic3RzIjoiYWN0aXZlIiwic3ViIjoidXNlcl8zRFFEaE1TYkpsQTdaaVR5S1hYeGxRaGpjMDgiLCJ2IjoyfQ.DFLPnOXZjIBY0vpsM5x8XKQPl5TKevsu6-isXrh6Jiq7Z7FwErwVtz0QeUOOUCQeyV9d5NtjPPasxRMiYJ2dh7DWHRH606s9SURGZL6KkxnmO_wUrV1gVhD-1PD38aBsUSTk2ei5_6namZWfkAf6Ey2U6rdn_Z0bFaUadpVD2cfJuEkbqBGay8IKxesbc13decv_EG_s-qRlaWskiQlXJtHzBO7aYZFDOHmWxG6xNRyg5MnjIcGP2FVYA51oGfzXwpwHKy_t4rbwbJW4Rwwt8t9Tw7RwlYNQkfx8j53h04Vz_S4TfEuD8U_js0V5NfKw1-DfvQHC0Sxlt-8olnDXwA"

'''