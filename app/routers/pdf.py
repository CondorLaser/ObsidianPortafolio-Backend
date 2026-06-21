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
from fastapi.responses import JSONResponse
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

from scripts.warnings_module import warnings
from app.repositories.portfolio_repo import reconstruct_user_portfolio
from app.routers.portfolio import (
    post_daily_portfolio_metrics,
    post_monthly_portfolio_metrics,
)
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
    print("1 - Recibido upload PDF stocks/ETF 1")
    await _require_account(db, user, account_id)
    print("2 - Cuenta validada")
    content = await file.read()
    print(f"3 - Archivo leído ({len(content)} bytes)")
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            data = extract_stocks_etf_1(pdf)
        print("4 - PDF procesado correctamente")
    except Exception as e:
        print(f"ERROR procesando PDF: {e}")
        raise HTTPException(
            status_code=400,
            detail="Error al analizar el archivo, archivo no válido"
        )
    print("5 - Guardando transactions/dividends")
    dict_processed_data = await pdf_repo.stocks_etf_1( db, user.clerk_id, data, account_id)
    print("6 - Transactions guardadas")

    if (
        dict_processed_data.get("compras_ventas_guardadas", 0) == 0
        and dict_processed_data.get("dividendos_guardados", 0) == 0
    ):
        return JSONResponse(
            status_code=422,
            content={
                "message": (
                    "No se subieron transacciones, revisa que sea el archivo correcto"
                ),
            }
        )

    try:
        print("7 - Iniciando reconstrucción de portafolio")
        n_snapshots, n_positions = await reconstruct_user_portfolio(db,user)
        print(
            f"8 - Reconstrucción OK "
            f"(snapshots={n_snapshots}, positions={n_positions})"
        )
        print("9 - Creando métricas diarias")
        daily_metrics = await post_daily_portfolio_metrics(user,db)
        print(f"10 - Daily metrics OK: {daily_metrics}")
        print("11 - Creando métricas mensuales")
        monthly_metrics = await post_monthly_portfolio_metrics(user,db)
        print(f"12 - Monthly metrics OK: {monthly_metrics}")

                # Generate warnings based on updated portfolio
        print("13 - Generando warnings")
        warnings_found = await warnings(db, user.clerk_id, send_mail=True)

        print("14 - Todo completado exitosamente")

        return {
            "message": (
                "Certificado de Transacciones procesado, "
                "transacciones y portafolio reconstruido con éxito"
            ),
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
        print(f"ERROR EN RECONSTRUCCIÓN/MÉTRICAS: {type(e).__name__}")
        print(f"DETALLE: {e}")

        return {
            "message": (
                "Certificado procesado, pero la reconstrucción "
                "inmediata falló. Se ejecutará durante la noche"
            ),
            "error": str(e)
        }


@router.post("/extract_mutual_funds")
async def upload_pdf_mutual_funds(
    file: UploadFile = File(...),
    account_id: uuid.UUID = Form(...),
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    print("1 - Recibido upload PDF FUND")
    await _require_account(db, user, account_id)
    print("2 - Cuenta validada")
    content = await file.read()
    print(f"3 - Archivo leído ({len(content)} bytes)")
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            data = extract_mutual_funds(pdf)
            print("4 - PDF procesado correctamente")
    except Exception as e:
        print(f"ERROR procesando PDF: {e}")
        raise HTTPException(status_code=400, detail="Error al analizar el archivo, archivo no válido")
    # Generar las Transactions (aportes/rescates de fondos mutuos)
    print("5 - Guardando transactions/dividends")
    #await pdf_repo.save_mutual_funds(db, user.clerk_id, data, account_id)
    print("6 - Transactions guardadas")
    result = await pdf_repo.save_mutual_funds(db, user.clerk_id, data, account_id)

    if result.get("compras_ventas_guardadas", 0) == 0:
        return JSONResponse(
            status_code=422,
            content={
                "message": (
                    "No se subieron transacciones, revisa que sea el archivo correcto."
                ),
            },
        )

    # Reconstruir portafolio en base a eso (positions + snapshot portafolio)
    try:
        print("7 - Iniciando reconstrucción de portafolio")
        n_snapshots, n_positions = await reconstruct_user_portfolio(db, user)
        print(
            f"8 - Reconstrucción OK "
            f"(snapshots={n_snapshots}, positions={n_positions})"
        )
        print("9 - Creando métricas diarias")
        daily_metrics = await post_daily_portfolio_metrics(user, db)
        print(f"10 - Daily metrics OK: {daily_metrics}")
        print("11 - Creando métricas mensuales")
        monthly_metrics = await post_monthly_portfolio_metrics(user, db)
        print(f"12 - Monthly metrics OK: {monthly_metrics}")
        print("13 - Generando warnings")
        warnings_found = await warnings(db, user.clerk_id, send_mail=True)
        print("14 - Todo completado exitosamente")  
        
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
