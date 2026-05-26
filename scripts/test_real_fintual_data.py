"""Test de ingestion con DATA REAL de los certificados Fintual del usuario.

Las rows se construyen 1:1 a partir de los PDFs reales adjuntos por el usuario
(extraídos manualmente del texto, antes de pdfplumber). Esto valida la cadena
completa de persistencia EXCEPTO la extracción pdfplumber.

Para testear pdfplumber, usar `scripts/test_pdf_e2e.py` (requiere los PDFs en
disco).

Uso:
    ./venv/bin/python -m scripts.test_real_fintual_data

Limpia su propia data al final (prefijo _real_fintual_).
"""
import asyncio
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.models.account import Account
from app.models.asset import Asset, AssetKind
from app.models.transaction import Transaction
from app.models.user import Profile
from app.repositories import account_repo, asset_repo, pdf_repo, user_repo
from app.schemas.account import AccountCreate
from app.schemas.asset import AssetCreate


TEST_PREFIX = "_real_fintual_"


# ────────────────────────────────────────────────────────────────────────────
# Data EXACTA del certificado.pdf (stocks/ETFs + dividendos)
# Cada row sigue el formato que produce processing_pdf.extract_stocks_etf_1:
# purchase_sales: [fecha, nombre, simbolo, categoria, aporte, acc_compradas, rescate, acc_vendidas]
# dividends:      [fecha, nombre, simbolo, categoria, gross, impuestos, neto]
# ────────────────────────────────────────────────────────────────────────────
PURCHASE_SALES = [
    # 2025
    ["2025-03-12", "Apple Inc. Common Stock", "AAPL", "Acciones", 10.0, 0.046107171, 0.0, 0.0],
    ["2025-03-12", "JPMorgan BetaBuilders Developed Asia Pacific-ex Japan ETF", "BBAX", "ETF", 10.0, 0.204198317, 0.0, 0.0],
    ["2025-03-12", "Invesco QQQ Trust, Series 1", "QQQ", "ETF", 10.0, 0.020979930, 0.0, 0.0],
    ["2025-03-12", "State Street SPDR S&P 500 ETF Trust", "SPY", "ETF", 10.0, 0.017900231, 0.0, 0.0],
    ["2025-03-12", "State Street SPDR Bloomberg 1-3 Month T-Bill ETF", "BIL", "ETF", 10.0, 0.109244248, 0.0, 0.0],
    ["2025-03-14", "Apple Inc. Common Stock", "AAPL", "Acciones", 10.0, 0.046904315, 0.0, 0.0],
    ["2025-03-15", "iShares Core S&P 500 ETF", "IVV", "ETF", 20.0, 0.035372561, 0.0, 0.0],
    ["2025-03-15", "NVIDIA Corporation Common Stock", "NVDA", "Acciones", 20.0, 0.163025758, 0.0, 0.0],
    ["2025-03-20", "iShares U.S. Energy ETF", "IYE", "ETF", 1.0, 0.020691082, 0.0, 0.0],
    ["2025-03-20", "Banco de Chile ADS", "BCH", "Acciones", 1.0, 0.035124692, 0.0, 0.0],
    ["2025-03-20", "iShares U.S. Healthcare ETF", "IYH", "ETF", 10.0, 0.163542995, 0.0, 0.0],
    ["2025-03-20", "iShares MSCI USA Min Vol Factor ETF", "USMV", "ETF", 10.0, 0.108297775, 0.0, 0.0],
    ["2025-03-20", "iShares 3-7 Year Treasury Bond ETF", "IEI", "ETF", 10.0, 0.084977650, 0.0, 0.0],
    ["2025-03-21", "Tesla, Inc. Common Stock", "TSLA", "Acciones", 20.0, 0.083638614, 0.0, 0.0],
    ["2025-03-26", "iShares U.S. Healthcare ETF", "IYH", "ETF", 10.0, 0.165289256, 0.0, 0.0],
    ["2025-03-27", "iShares MSCI China ETF", "MCHI", "ETF", 2.89, 0.052222623, 0.0, 0.0],
    ["2025-03-27", "iShares Core S&P 500 ETF", "IVV", "ETF", 50.0, 0.087548501, 0.0, 0.0],
    ["2025-04-03", "iShares Core S&P 500 ETF", "IVV", "ETF", 700.0, 1.285045013, 0.0, 0.0],
    ["2025-04-03", "Apple Inc. Common Stock", "AAPL", "Acciones", 68.0, 0.331810906, 0.0, 0.0],
    ["2025-04-03", "iShares MSCI China ETF", "MCHI", "ETF", 100.0, 1.865393224, 0.0, 0.0],
    ["2025-04-03", "NVIDIA Corporation Common Stock", "NVDA", "Acciones", 40.0, 0.389036939, 0.0, 0.0],
    ["2025-04-04", "iShares Core S&P 500 ETF", "IVV", "ETF", 100.0, 0.190733408, 0.0, 0.0],
    ["2025-04-23", "SPDR Gold Trust", "GLD", "ETF", 45.0, 0.148120840, 0.0, 0.0],
    ["2025-06-25", "iShares MSCI China ETF", "MCHI", "ETF", 0.88, 0.015848431, 0.0, 0.0],
    ["2025-06-25", "iShares Core S&P 500 ETF", "IVV", "ETF", 2.54, 0.004158398, 0.0, 0.0],
    ["2025-08-13", "Figma, Inc.", "FIG", "Acciones", 2.70, 0.029725861, 0.0, 0.0],
    ["2025-09-24", "iShares Core S&P 500 ETF", "IVV", "ETF", 2.72, 0.004073563, 0.0, 0.0],
    # Sell ahora:
    ["2025-10-08", "iShares Core S&P 500 ETF", "IVV", "ETF", 0.0, 0.0, 200.07, 0.297070881],
    ["2025-12-24", "iShares Core S&P 500 ETF", "IVV", "ETF", 2.69, 0.003879904, 0.0, 0.0],
    ["2025-12-24", "iShares MSCI China ETF", "MCHI", "ETF", 1.21, 0.019875164, 0.0, 0.0],
    # 2026
    ["2026-01-06", "Exxon Mobil Corporation", "XOM", "Acciones", 20.0, 0.159489633, 0.0, 0.0],
    ["2026-02-06", "State Street SPDR S&P 500 ETF Trust", "SPY", "ETF", 0.0, 0.0, 12.20, 0.017900231],
    ["2026-03-12", "Vanguard FTSE All-World Ex-US ETF", "VEU", "ETF", 95.42, 1.261368443, 0.0, 0.0],
    ["2026-03-18", "Take-Two Interactive Software, Inc.", "TTWO", "Acciones", 80.0, 0.387882549, 0.0, 0.0],
    ["2026-03-25", "iShares Core S&P 500 ETF", "IVV", "ETF", 1.99, 0.003037565, 0.0, 0.0],
    ["2026-03-26", "Tesla, Inc. Common Stock", "TSLA", "Acciones", 60.0, 0.162249864, 0.0, 0.0],
]

DIVIDENDS = [
    ["2025-03-21", "iShares Core S&P 500 ETF", "IVV", "ETF", 0.06, 0.00, 0.06],
    ["2025-03-27", "JPMorgan BetaBuilders Asia Pacific", "BBAX", "ETF", 0.09, 0.01, 0.08],
    ["2025-04-03", "Banco de Chile ADS", "BCH", "Acciones", 0.06, 0.00, 0.06],
    ["2025-04-04", "SPDR Bloomberg T-Bill", "BIL", "ETF", 0.04, 0.00, 0.04],
    ["2025-04-04", "iShares 3-7 Year Treasury Bond ETF", "IEI", "ETF", 0.03, 0.00, 0.03],
    ["2025-04-30", "SPDR S&P 500 ETF Trust", "SPY", "ETF", 0.03, 0.00, 0.03],
    ["2025-04-30", "Invesco QQQ Trust", "QQQ", "ETF", 0.02, 0.00, 0.02],
    ["2025-05-15", "Apple Inc.", "AAPL", "Acciones", 0.11, 0.01, 0.10],
    ["2025-06-20", "iShares U.S. Healthcare ETF", "IYH", "ETF", 0.06, 0.00, 0.06],
    ["2025-06-20", "iShares MSCI China ETF", "MCHI", "ETF", 1.03, 0.15, 0.88],
    ["2025-06-20", "iShares Core S&P 500 ETF", "IVV", "ETF", 2.98, 0.44, 2.54],
    ["2025-06-20", "iShares U.S. Energy ETF", "IYE", "ETF", 0.01, 0.00, 0.01],
    ["2025-06-20", "iShares MSCI USA Min Vol Factor ETF", "USMV", "ETF", 0.04, 0.00, 0.04],
    ["2025-07-03", "NVIDIA Corporation", "NVDA", "Acciones", 0.01, 0.00, 0.01],
    ["2025-08-14", "Apple Inc.", "AAPL", "Acciones", 0.11, 0.01, 0.10],
    ["2025-09-19", "iShares U.S. Healthcare ETF", "IYH", "ETF", 0.06, 0.00, 0.06],
    ["2025-09-19", "iShares U.S. Energy ETF", "IYE", "ETF", 0.01, 0.00, 0.01],
    ["2025-09-19", "iShares Core S&P 500 ETF", "IVV", "ETF", 3.20, 0.48, 2.72],
    ["2025-09-19", "iShares MSCI USA Min Vol Factor ETF", "USMV", "ETF", 0.04, 0.00, 0.04],
    ["2025-11-13", "Apple Inc.", "AAPL", "Acciones", 0.11, 0.01, 0.10],
    ["2025-12-19", "iShares Core S&P 500 ETF", "IVV", "ETF", 3.16, 0.47, 2.69],
    ["2025-12-19", "iShares MSCI China ETF", "MCHI", "ETF", 1.42, 0.21, 1.21],
    ["2026-01-30", "SPDR S&P 500 ETF Trust", "SPY", "ETF", 0.04, 0.00, 0.04],
    ["2026-02-12", "Apple Inc.", "AAPL", "Acciones", 0.11, 0.01, 0.10],
    ["2026-03-10", "Exxon Mobil Corporation", "XOM", "Acciones", 0.16, 0.02, 0.14],
    ["2026-03-20", "iShares Core S&P 500 ETF", "IVV", "ETF", 2.34, 0.35, 1.99],
    ["2026-03-24", "Vanguard FTSE All-World Ex-US ETF", "VEU", "ETF", 0.14, 0.02, 0.12],
    ["2026-04-01", "NVIDIA Corporation", "NVDA", "Acciones", 0.01, 0.00, 0.01],
    ["2026-04-13", "Banco de Chile ADS", "BCH", "Acciones", 0.06, 0.00, 0.06],
]


# ────────────────────────────────────────────────────────────────────────────
# Data del certificado_de_transacciones.pdf (fondos mutuos)
# Formato extract_mutual_funds:
# [fecha, nombre_inversion, nombre_fondo, serie_fondo, aportes_cuotas, rescate_cuotas, aportes_pesos, rescate_pesos]
# Fecha DD/MM/YYYY
# ────────────────────────────────────────────────────────────────────────────
MUTUAL_FUNDS = [
    ["13/03/2026", "Reserva", "Very Conservative Streep", "A", 703.8683, 0.0, 1000000.0, 0.0],
    ["13/03/2026", "Pension Millonaria APV-A", "Risky Norris", "APV", 8.7562, 0.0, 30000.0, 0.0],
    ["13/03/2026", "Savings to invest", "Moderate Pitt", "A", 348.1641, 0.0, 840000.0, 0.0],
    ["13/03/2026", "Savings to invest", "Conservative Clooney", "A", 97.7151, 0.0, 160000.0, 0.0],
    ["12/03/2026", "Maximo Colegio", "Risky Norris", "A", 37.9035, 0.0, 126000.0, 0.0],
    ["12/03/2026", "Maximo Colegio", "Moderate Pitt", "A", 30.6115, 0.0, 74000.0, 0.0],
    ["04/03/2026", "Alto Riesgo", "Risky Norris", "A", 14.8865, 0.0, 50000.0, 0.0],
    ["24/02/2026", "Inversion 1", "Moderate Pitt", "A", 0.0, 9.9750, 0.0, 23766.0],
    ["24/02/2026", "Inversion 1", "Conservative Clooney", "A", 0.0, 13.0380, 0.0, 21234.0],
    ["21/01/2026", "Alto Riesgo", "Risky Norris", "A", 0.0, 60.2254, 0.0, 200000.0],
    ["19/01/2026", "Alto Riesgo", "Risky Norris", "A", 0.0, 59.4286, 0.0, 200000.0],
    ["02/12/2025", "Inversion 1", "Moderate Pitt", "A", 0.0, 17.9593, 0.0, 44372.0],
    ["02/12/2025", "Inversion 1", "Conservative Clooney", "A", 0.0, 21.8268, 0.0, 35628.0],
    ["08/10/2025", "Inversion 1", "Moderate Pitt", "A", 0.0, 23.4173, 0.0, 58241.0],
    ["08/10/2025", "Inversion 1", "Conservative Clooney", "A", 0.0, 25.6220, 0.0, 41759.0],
    ["06/10/2025", "Reserva", "Very Conservative Streep", "A", 0.0, 42.9358, 0.0, 60000.0],
    ["03/10/2025", "Alto Riesgo", "Risky Norris", "A", 14.4504, 0.0, 50000.0, 0.0],
]


async def setup_assets(symbols_etf: dict, fund_assets: dict):
    """Crea los assets necesarios para que el lookup funcione."""
    async with SessionLocal() as db:
        # Stocks/ETFs por symbol único
        for sym, (name, kind) in symbols_etf.items():
            existing = await asset_repo.get_by_symbol_and_kind(db, sym, kind)
            if existing is None:
                await asset_repo.create(
                    db,
                    AssetCreate(symbol=sym, name=name, kind=kind, currency="USD"),
                )
        # Fondos mutuos por (name, symbol=series)
        for (name, series), category in fund_assets.items():
            # Si ya existe con esta combinación, skip
            from sqlalchemy import select
            from app.models.asset import Asset as AssetModel
            existing = await db.execute(
                select(AssetModel).where(
                    AssetModel.name == name,
                    AssetModel.symbol == series,
                    AssetModel.kind == AssetKind.fund,
                )
            )
            if existing.scalar_one_or_none() is None:
                await asset_repo.create(
                    db,
                    AssetCreate(symbol=series, name=name, kind=AssetKind.fund, currency="CLP"),
                )


async def cleanup():
    """Borra todo lo creado con TEST_PREFIX."""
    from app.models.user_preference import UserPreference
    from app.models.portfolio_snapshot import PortfolioSnapshot

    async with SessionLocal() as db:
        await db.execute(
            delete(Account).where(Account.user_id.like(f"{TEST_PREFIX}%"))
        )
        await db.execute(
            delete(UserPreference).where(UserPreference.user_id.like(f"{TEST_PREFIX}%"))
        )
        await db.execute(
            delete(PortfolioSnapshot).where(PortfolioSnapshot.user_id.like(f"{TEST_PREFIX}%"))
        )
        await db.execute(
            delete(Profile).where(Profile.clerk_id.like(f"{TEST_PREFIX}%"))
        )
        await db.commit()


async def main():
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║  TEST: ingestion con DATA REAL de certificados Fintual           ║")
    print("╚══════════════════════════════════════════════════════════════════╝")

    # ─── Setup assets necesarios ──────────────────────────────────────────
    stock_etf_assets = {row[2]: (row[1], AssetKind.stock if row[3] == "Acciones" else AssetKind.etf)
                        for row in PURCHASE_SALES}
    fund_assets = {(row[2], row[3]): "fund" for row in MUTUAL_FUNDS}

    print(f"\nAssets a crear: {len(stock_etf_assets)} stocks/ETFs + {len(fund_assets)} fondos")
    await setup_assets(stock_etf_assets, fund_assets)

    # ─── Crear user + accounts ────────────────────────────────────────────
    u_id = f"{TEST_PREFIX}max"
    async with SessionLocal() as db:
        u = await user_repo.get_or_create_by_clerk_id(db, u_id, "max@real.test")
        acc_stocks = await account_repo.create(
            db, u_id, AccountCreate(name="Fintual Acciones+ETFs", broker="Fintual", currency="USD")
        )
        acc_funds = await account_repo.create(
            db, u_id, AccountCreate(name="Fintual Fondos Mutuos", broker="Fintual", currency="CLP")
        )

    # ─── Fase A: stocks/ETFs ──────────────────────────────────────────────
    print(f"\n━━━ Stocks/ETFs ({len(PURCHASE_SALES)} compraventas + {len(DIVIDENDS)} dividendos) ━━━")
    async with SessionLocal() as db:
        result = await pdf_repo.stocks_etf_1(
            db, u_id, [PURCHASE_SALES, DIVIDENDS], acc_stocks.id
        )
    print(f"  compraventas guardadas: {result['compras_ventas_guardadas']} / {len(PURCHASE_SALES)}")
    print(f"  dividendos guardados:   {result['dividendos_guardados']} / {len(DIVIDENDS)}")
    print(f"  símbolos faltantes:     {result['errores_activos_faltantes']}")
    assert result["compras_ventas_guardadas"] == len(PURCHASE_SALES), \
        f"FAIL compraventas: {result}"
    assert result["dividendos_guardados"] == len(DIVIDENDS), \
        f"FAIL dividendos: {result}"
    print("  ✅ Stocks/ETFs persistidos OK")

    # ─── Fase B: mutual funds ─────────────────────────────────────────────
    print(f"\n━━━ Fondos Mutuos ({len(MUTUAL_FUNDS)} movimientos) ━━━")
    async with SessionLocal() as db:
        result = await pdf_repo.save_mutual_funds(db, u_id, MUTUAL_FUNDS, acc_funds.id)
    print(f"  movimientos guardados: {result['compras_ventas_guardadas']} / {len(MUTUAL_FUNDS)}")
    print(f"  fondos faltantes:      {result['errores_activos_faltantes']}")
    assert result["compras_ventas_guardadas"] == len(MUTUAL_FUNDS), \
        f"FAIL mutual_funds: {result}"
    print("  ✅ Fondos mutuos persistidos OK")

    # ─── Verificación: counts en DB ───────────────────────────────────────
    print("\n━━━ Verificación en DB ━━━")
    async with SessionLocal() as db:
        det_stocks = await account_repo.get_for_user_with_detail(db, u_id, acc_stocks.id)
        det_funds = await account_repo.get_for_user_with_detail(db, u_id, acc_funds.id)
        tx_stocks = len(det_stocks.transactions)
        div_stocks = len(det_stocks.dividends)
        tx_funds = len(det_funds.transactions)
        # Verificar buy/sell breakdown en stocks
        buys = sum(1 for t in det_stocks.transactions if t.kind.value == "buy")
        sells = sum(1 for t in det_stocks.transactions if t.kind.value == "sell")
    print(f"  account_stocks: {tx_stocks} transactions ({buys} buy + {sells} sell) + {div_stocks} dividends")
    print(f"  account_funds:  {tx_funds} transactions")
    print(f"  ✅ Data real Fintual ingestada y queryable end-to-end")

    # ─── Cleanup ──────────────────────────────────────────────────────────
    print("\n━━━ Cleanup ━━━")
    await cleanup()
    print("  ✅ test data borrada (prefix _real_fintual_)")

    print("\n🎉 INGESTA REAL FINTUAL: TODOS LOS CHECKS PASARON")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
