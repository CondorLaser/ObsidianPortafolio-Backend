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
from app.models.user import Profile
from app.repositories import account_repo, pdf_repo
from scripts.processing_pdf import (
    extract_mutual_funds,
    extract_stocks_etf_1,
    extract_stocks_etf_2,
)
from app.repositories.portfolio_repo import reconstruct_user_portfolio
from scripts.warnings_module import warnings


router = APIRouter(prefix="/pdf", tags=["pdf"])


async def _require_account(db: AsyncSession, user: Profile, account_id: uuid.UUID):
    account = await account_repo.get_for_user(db, user.clerk_id, account_id)
    if not account:
        raise HTTPException(status_code=403, detail="Cuenta no autorizada")
    return account


@router.post("/extract_stocks_etf_1")
async def upload_pdf_stocks_etf_1(
    file: UploadFile = File(...),
    account_id: uuid.UUID = Form(...),
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_account(db, user, account_id)
    content = await file.read()
    
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            data = extract_stocks_etf_1(pdf)
    except Exception:
        raise HTTPException(status_code=400, detail="Error al analizar el archivo, archivo no válido")
    # Generar las Transactions y Dividends
    dict_processed_data = await pdf_repo.stocks_etf_1(db, user.clerk_id, data, account_id)
    # Reconstruir portafolio en base a eso (positions + snapshot portafolio)
    try:
        n_snapshots, n_positions = await reconstruct_user_portfolio(db, user.clerk_id)
        
        # Generate warnings based on updated portfolio
        warnings_found = await warnings(db, user.clerk_id, send_mail=True)

        print({"reconstruction_details": {
                "snapshots_updated": n_snapshots,
                "positions_updated": n_positions
            },
            "processed_data": dict_processed_data,
            "warnings_generated": len(warnings_found)})
        
        return {
            "message": "Certificado de Transacciones procesado, transacciones y portafolio reconstruido con éxito",
            "reconstruction_details": {
                "snapshots_updated": n_snapshots,
                "positions_updated": n_positions
            },
            "warnings": {
                "count": len(warnings_found),
                "items": warnings_found
            },
            "processed_data": dict_processed_data
        }
    except Exception as e:
        return {
            "message": "Certificado procesado, pero la reconstrucción inmediata falló. Se ejecutará durante la noche",
            "error": str(e)
        }


@router.post("/extract_mutual_funds")
async def upload_pdf_mutual_funds(
    file: UploadFile = File(...),
    account_id: uuid.UUID = Form(...),
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_account(db, user, account_id)
    content = await file.read()
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            data = extract_mutual_funds(pdf)
    except Exception:
        raise HTTPException(status_code=400, detail="Error al analizar el archivo, archivo no válido")
    # Generar las Transactions (aportes/rescates de fondos mutuos)
    await pdf_repo.save_mutual_funds(db, user.clerk_id, data, account_id)
    # Reconstruir portafolio en base a eso (positions + snapshot portafolio)
    try:
        n_snapshots, n_positions = await reconstruct_user_portfolio(db, user.clerk_id)
        
        # Generate warnings based on updated portfolio
        warnings_found = await warnings(db, user.clerk_id, send_mail=True)
        
        return {
            "message": "Certificado de Transacciones procesado, transacciones y portafolio reconstruido con éxito",
            "reconstruction_details": {
                "snapshots_updated": n_snapshots,
                "positions_updated": n_positions
            },
            "warnings": {
                "count": len(warnings_found),
                "items": warnings_found
            }
        }
    except Exception as e:
        return {
            "message": "Certificado procesado, pero la reconstrucción inmediata falló. Se ejecutará durante la noche",
            "error": str(e)
        }


@router.post("/extract_stocks_etf_2")
async def upload_pdf_stocks_etf_2(
    file: UploadFile = File(...),
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            data = extract_stocks_etf_2(pdf)
    except Exception:
        raise HTTPException(status_code=400, detail="Error al analizar el archivo, archivo no válido")
    return await pdf_repo.stocks_etf_2(db, user.clerk_id, data)
