from fastapi import APIRouter, Depends
from fastapi import HTTPException
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


'''

Comando para testear:

curl -X GET http://localhost:8000/accounts -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsImNhdCI6ImNsX0I3ZDRQRDExMUFBQSIsImtpZCI6Imluc18zQ1VXOWx6QVQyUGtTbXVnRWxiZ2E4bnFnQjAiLCJvaWF0IjoxNzc5MjI5NjY1LCJ0eXAiOiJKV1QifQ.eyJhenAiOiJodHRwczovL29ic2lkaWFuLXBvcnRhZm9saW8tZnJvbnRlbmQudmVyY2VsLmFwcCIsImV4cCI6MTc3OTIyOTcyNSwiZnZhIjpbMTksLTFdLCJpYXQiOjE3NzkyMjk2NjUsImlzcyI6Imh0dHBzOi8vd29ydGh5LWphY2thbC04MC5jbGVyay5hY2NvdW50cy5kZXYiLCJuYmYiOjE3NzkyMjk2NTUsInNpZCI6InNlc3NfM0R4ZkNHSXBmdnVvZHljYTVxVGZ5NDdUeFVmIiwic3RzIjoiYWN0aXZlIiwic3ViIjoidXNlcl8zRFFEaE1TYkpsQTdaaVR5S1hYeGxRaGpjMDgiLCJ2IjoyfQ.RuONtp95fpLgdYdPuL4MAWl2QMEC9EQQp7p-dhE0Nnyq2yqqWiCOGYb4yNwli1Iwf5qNOYittEyY0cOF4_uGMUhc-V4GKk-oG1bEQ1ScHRRumqUvbzLMOC4ZMiZiSlR-FOIwb0774gGLZFGTx_sRQtOt8K9SYTIcDw9W47liFu3-QIpGSe326mn-sWIl-CKCl3i-HOdV5PcS4aW8Enl5HKyVll_nbPpLlhNlmJZJZ3TSkXgnC91I-kmZ6XEJFihB6c4SBUpMKB_3bOJ3xZvGM5mELAgHOrAdyOM4NF1XAjS9HJPBlpkkTvxShLfv0vcuRUoftL_m9SAKzZyvuDkYNQ"

'''