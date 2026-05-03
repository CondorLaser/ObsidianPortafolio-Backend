from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

#from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.repositories import account_repo
from app.schemas.account import AccountCreate, AccountRead
import pdfplumber
from scripts.processing_pdf import extract_stocks_etf_1, extract_mutual_funds, extract_stocks_etf_2
import io

router = APIRouter(prefix="/pdf", tags=["pdf"])



async def get_current_user():
    class FakeUser:
        id = 1
    return FakeUser()



@router.post("/extract_stocks_etf_1")
async def upload_pdf_type1(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        data = extract_stocks_etf_1(pdf)  
    
    #result = await pdf_repo.save_pdf_type_1(db, user.id, data)
    return data

#@router.post("/type2")
#async def upload_pdf_type2(): pass


#@router.post("/type3")
#async def upload_pdf_type3(): pass
