"""Test end-to-end de ingestión de PDFs Fintual REALES.

Requiere los PDFs en disco:
    /Users/mtombolini/Desktop/cert_stocks.pdf   (stocks/ETFs + dividendos)
    /Users/mtombolini/Desktop/cert_funds.pdf    (fondos mutuos)

Cubre la cadena completa:
    PDF → pdfplumber → processing_pdf.extract_* → pdf_repo → DB

Uso:
    ./venv/bin/python -m scripts.test_pdf_e2e

Limpia su propia data al final (prefix _pdf_e2e_).
"""
import asyncio
import sys
from pathlib import Path

import pdfplumber
from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models.account import Account
from app.models.asset import Asset, AssetKind
from app.models.user import Profile
from app.repositories import account_repo, asset_repo, pdf_repo, user_repo
from app.schemas.account import AccountCreate
from app.schemas.asset import AssetCreate
from scripts.processing_pdf import (
    extract_mutual_funds,
    extract_stocks_etf_1,
)

TEST_PREFIX = "_pdf_e2e_"
PDF_STOCKS = Path("/Users/mtombolini/Desktop/cert_stocks.pdf")
PDF_FUNDS = Path("/Users/mtombolini/Desktop/cert_funds.pdf")


async def cleanup():
    from app.models.user_preference import UserPreference
    from app.models.portfolio_snapshot import PortfolioSnapshot
    async with SessionLocal() as db:
        await db.execute(
            delete(Account).where(Account.user_id.like(f"{TEST_PREFIX}%"))
        )
        await db.execute(
            delete(UserPreference).where(
                UserPreference.user_id.like(f"{TEST_PREFIX}%")
            )
        )
        await db.execute(
            delete(PortfolioSnapshot).where(
                PortfolioSnapshot.user_id.like(f"{TEST_PREFIX}%")
            )
        )
        await db.execute(
            delete(Profile).where(Profile.clerk_id.like(f"{TEST_PREFIX}%"))
        )
        await db.commit()


async def setup_assets_from_extracted(purchase_sales: list, dividends_rows: list, fund_rows: list):
    """Crea los assets necesarios basándose en lo que pdfplumber extrajo."""
    # Stocks/ETFs
    symbols = {(row[2], "ETF" if row[3] == "ETF" else "Acciones"): row[1] for row in purchase_sales}
    async with SessionLocal() as db:
        for (sym, cat), name in symbols.items():
            kind = AssetKind.etf if cat == "ETF" else AssetKind.stock
            existing = await asset_repo.get_by_symbol_and_kind(db, sym, kind)
            if existing is None:
                await asset_repo.create(
                    db,
                    AssetCreate(symbol=sym, name=name, kind=kind, currency="USD"),
                )

        # Fondos mutuos (name + series)
        fund_keys = {(row[2], row[3]) for row in fund_rows}
        for (name, series) in fund_keys:
            existing = await db.execute(
                select(Asset).where(
                    Asset.name == name,
                    Asset.symbol == series,
                    Asset.kind == AssetKind.fund,
                )
            )
            if existing.scalar_one_or_none() is None:
                await asset_repo.create(
                    db,
                    AssetCreate(symbol=series, name=name, kind=AssetKind.fund, currency="CLP"),
                )


async def main():
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║  TEST E2E: PDFs Fintual REALES (pdfplumber → repo → DB)          ║")
    print("╚══════════════════════════════════════════════════════════════════╝")

    if not PDF_STOCKS.exists():
        print(f"\n❌ No encuentro {PDF_STOCKS}")
        print("   Guardá el certificado.pdf (stocks/ETFs) en esa ruta.")
        return 1
    if not PDF_FUNDS.exists():
        print(f"\n❌ No encuentro {PDF_FUNDS}")
        print("   Guardá el certificado_de_transacciones.pdf (fondos) en esa ruta.")
        return 1

    print(f"\n✅ PDF stocks/ETFs:  {PDF_STOCKS} ({PDF_STOCKS.stat().st_size:,} bytes)")
    print(f"✅ PDF fondos:      {PDF_FUNDS}  ({PDF_FUNDS.stat().st_size:,} bytes)")

    # ─── Extraer con pdfplumber ───────────────────────────────────────────
    print("\n━━━ pdfplumber → processing_pdf.extract_* ━━━")
    with pdfplumber.open(PDF_STOCKS) as pdf:
        purchase_sales, dividends_rows = extract_stocks_etf_1(pdf)
    print(f"  cert_stocks.pdf: {len(purchase_sales)} compraventas + {len(dividends_rows)} dividendos")

    with pdfplumber.open(PDF_FUNDS) as pdf:
        fund_rows = extract_mutual_funds(pdf)
    print(f"  cert_funds.pdf:  {len(fund_rows)} movimientos de fondos")

    if not purchase_sales:
        print("  ❌ pdfplumber NO extrajo compraventas (¿formato cambió?)")
        return 1

    # ─── Setup assets + user ──────────────────────────────────────────────
    await setup_assets_from_extracted(purchase_sales, dividends_rows, fund_rows)
    u_id = f"{TEST_PREFIX}max"
    async with SessionLocal() as db:
        u = await user_repo.get_or_create_by_clerk_id(db, u_id, "max@pdf_e2e.test")
        acc_stocks = await account_repo.create(
            db, u_id, AccountCreate(name="Fintual Acciones+ETFs", broker="Fintual", currency="USD")
        )
        acc_funds = await account_repo.create(
            db, u_id, AccountCreate(name="Fintual Fondos", broker="Fintual", currency="CLP")
        )

    # ─── pdf_repo persiste ────────────────────────────────────────────────
    print("\n━━━ pdf_repo persiste ━━━")
    async with SessionLocal() as db:
        result_stocks = await pdf_repo.stocks_etf_1(
            db, u_id, [purchase_sales, dividends_rows], acc_stocks.id
        )
        result_funds = await pdf_repo.save_mutual_funds(
            db, u_id, fund_rows, acc_funds.id
        )

    print(f"  Stocks/ETFs: {result_stocks}")
    print(f"  Fondos:      {result_funds}")

    # ─── Verificación end-to-end ──────────────────────────────────────────
    print("\n━━━ Verificación en DB ━━━")
    async with SessionLocal() as db:
        det_stocks = await account_repo.get_for_user_with_detail(db, u_id, acc_stocks.id)
        det_funds = await account_repo.get_for_user_with_detail(db, u_id, acc_funds.id)
        buys = sum(1 for t in det_stocks.transactions if t.kind.value == "buy")
        sells = sum(1 for t in det_stocks.transactions if t.kind.value == "sell")
    print(f"  Stocks acc: {len(det_stocks.transactions)} tx ({buys} buy + {sells} sell)"
          f" + {len(det_stocks.dividends)} dividends")
    print(f"  Funds acc:  {len(det_funds.transactions)} tx")

    expected_stocks = result_stocks["compras_ventas_guardadas"]
    expected_funds = result_funds["compras_ventas_guardadas"]
    if (len(det_stocks.transactions) == expected_stocks
            and len(det_funds.transactions) == expected_funds):
        print("  ✅ Conteos matchean lo persistido")
    else:
        print(f"  ❌ Conteos NO matchean")

    # ─── Cleanup ──────────────────────────────────────────────────────────
    print("\n━━━ Cleanup ━━━")
    await cleanup()
    print(f"  ✅ test data borrada (prefix {TEST_PREFIX})")

    errors_stocks = result_stocks.get("errores_activos_faltantes", [])
    errors_funds = result_funds.get("errores_activos_faltantes", [])
    if errors_stocks or errors_funds:
        print(f"\n⚠️  símbolos no encontrados (esperado si pdfplumber extrajo nombres distintos):")
        if errors_stocks:
            print(f"   stocks: {errors_stocks}")
        if errors_funds:
            print(f"   funds:  {errors_funds}")

    print("\n🎉 PDF E2E TEST COMPLETO: pdfplumber → processing_pdf → pdf_repo → DB")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
