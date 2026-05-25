"""Endpoints de ingesta de PDFs (Fintual). Recibe un upload, lo parsea con
`scripts/processing_pdf.py` y persiste vía `pdf_repo`.

Bugs corregidos vs `ingesta_parte_1`:
- `HTTPException` no estaba importado (NameError al fallar el ownership check).
- Ruta `/extra t_stocks_etf_2` tenía un espacio literal → renombrada.
- Bloque `FakeUser` muerto eliminado.
"""
import io
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
import pdfplumber

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.repositories import account_repo, pdf_repo
from scripts.processing_pdf import (
    extract_mutual_funds,
    extract_stocks_etf_1,
    extract_stocks_etf_2,
)

router = APIRouter(prefix="/pdf", tags=["pdf"])


async def _require_account(db: AsyncSession, user: User, account_id: uuid.UUID):
    account = await account_repo.get_for_user(db, user.id, account_id)
    if not account:
        raise HTTPException(status_code=403, detail="Cuenta no autorizada")
    return account


@router.post("/extract_stocks_etf_1")
async def upload_pdf_stocks_etf_1(
    file: UploadFile = File(...),
    account_id: uuid.UUID = Form(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_account(db, user, account_id)
    content = await file.read()
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            data = extract_stocks_etf_1(pdf)
    except Exception:
        raise HTTPException(status_code=400, detail="Error al analizar el archivo, archivo no válido")
    return await pdf_repo.stocks_etf_1(db, user.id, data, account_id)


@router.post("/extract_mutual_funds")
async def upload_pdf_mutual_funds(
    file: UploadFile = File(...),
    account_id: uuid.UUID = Form(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_account(db, user, account_id)
    content = await file.read()
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            data = extract_mutual_funds(pdf)
    except Exception:
        raise HTTPException(status_code=400, detail="Error al analizar el archivo, archivo no válido")
    return await pdf_repo.save_mutual_funds(db, user.id, data, account_id)


@router.post("/extract_stocks_etf_2")
async def upload_pdf_stocks_etf_2(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            data = extract_stocks_etf_2(pdf)
    except Exception:
        raise HTTPException(status_code=400, detail="Error al analizar el archivo, archivo no válido")
    return await pdf_repo.stocks_etf_2(db, user.id, data)
