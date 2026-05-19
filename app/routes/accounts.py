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
            ORDER BY ex_date DESC
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
            ORDER BY transaction_date DESC
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

curl -X GET http://localhost:8000/accounts/4509d693-628a-484e-873e-ba3d214340b7 -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsImNhdCI6ImNsX0I3ZDRQRDExMUFBQSIsImtpZCI6Imluc18zQ1VXOWx6QVQyUGtTbXVnRWxiZ2E4bnFnQjAiLCJvaWF0IjoxNzc5MjMwMjg0LCJ0eXAiOiJKV1QifQ.eyJhenAiOiJodHRwczovL29ic2lkaWFuLXBvcnRhZm9saW8tZnJvbnRlbmQudmVyY2VsLmFwcCIsImV4cCI6MTc3OTIzMDM0NCwiZnZhIjpbMjksLTFdLCJpYXQiOjE3NzkyMzAyODQsImlzcyI6Imh0dHBzOi8vd29ydGh5LWphY2thbC04MC5jbGVyay5hY2NvdW50cy5kZXYiLCJuYmYiOjE3NzkyMzAyNzQsInNpZCI6InNlc3NfM0R4ZkNHSXBmdnVvZHljYTVxVGZ5NDdUeFVmIiwic3RzIjoiYWN0aXZlIiwic3ViIjoidXNlcl8zRFFEaE1TYkpsQTdaaVR5S1hYeGxRaGpjMDgiLCJ2IjoyfQ.nukC3W7dLwX2mh_mHWYmeMkz-EV3VbcACnVA-zOwGNLeIg7hnQOzU_aV-Hs6qa3b0GrHseaXATftL-ir4Qu60eBVD1par-CgFC-O0LCsiROcgrp2jvd_iGmvKmIa880H3owWbexx_JFLceS-IC8fZdIpKi3o2Xupw71gg-inoEoh-P8ETZDMBORb2oh-CEiu12iW9mRI66IWely_OPMp6cwatZikfxHd9XrG8HRXoUI8JQIVHGgNcm3yP55D7j4qjiRI_Mrj_lPFQW-ib1KIBDWGXpVt9oWZr9CMXFrd-zA-QRZRF-tHc7slYZma6u_u8IcM3eYDBeyNaQk0CFG0mg"

'''