from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.repositories import account_repo, pdf_repo
from app.schemas.account import AccountCreate, AccountRead
import pdfplumber
from scripts.processing_pdf import extract_stocks_etf_1, extract_mutual_funds, extract_stocks_etf_2
import io
from fastapi import Form
import uuid
router = APIRouter(prefix="/pdf", tags=["pdf"])


# DESCOMENTAR SI NO SE USA CLERK (VA A FALLAR POR EL TOKEN)
#async def get_current_user(): 
#    class FakeUser:
#        id = 1
#    return FakeUser()



@router.post("/extract_stocks_etf_1")
async def upload_pdf_type1(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    account_id: uuid.UUID = Form(...),
    db: AsyncSession = Depends(get_db)
):

    #verificar el usuario/cuenta 
    # ESTO NO SE HA PROBADO, YA QUE NO SE GUARDAN LOS USERS EN LA BDD COMENTAR PARA PROBAR
    account = await account_repo.get_for_user(db, user.id, account_id)
    if not account:
        raise HTTPException(status_code=403, detail="Cuenta no autorizada")

    content = await file.read()

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            data = extract_stocks_etf_1(pdf) #[Lista_compraventas, Lista_dividendos]
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Error al analizar el archivo, archivo no válido"
        )

    result = await pdf_repo.stocks_etf_1(db, user.id, data, account_id)
    return result

@router.post("/extract_mutual_funds")
async def upload_pdf_type2(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    account_id: uuid.UUID = Form(...),
):

    #verificar el usuario/cuenta
        # ESTO NO SE HA PROBADO, YA QUE NO SE GUARDAN LOS USERS EN LA BDD COMENTAR PARA PROBAR
    account = await account_repo.get_for_user(db, user.id, account_id)
    if not account:
        raise HTTPException(status_code=403, detail="Cuenta no autorizada")

    content = await file.read()
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            data = extract_mutual_funds(pdf)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Error al analizar el archivo, archivo no válido"
        )  
    
    result = await pdf_repo.save_mutual_funds(db, user.id, data, account_id)
    return result

@router.post("/extra t_stocks_etf_2")
async def upload_pdf_type3(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        data = extract_stocks_etf_2(pdf)  
    
    #result = await pdf_repo.save_pdf_type_1(db, user.id, data)
    return data
