"""Repos para ingesta de PDFs (Fintual). Recibe los rows ya extraídos por
`scripts/processing_pdf.py` y los persiste como `Transaction` y `Dividend`.

Bugs corregidos vs `ingesta_parte_1`:
- `stocks_etf_1` usaba `symbol` antes de definirlo (NameError). Ahora se piden
  todos los assets necesarios en una sola query con `Asset.symbol.in_(...)`.
- Activos no encontrados se devuelven en `errors` para que el caller los vea.
"""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset, AssetKind
from app.models.dividend import Dividend
from app.models.transaction import Transaction, TransactionKind


async def stocks_etf_1(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: list,
    account_id: uuid.UUID,
) -> dict:
    """Persiste compraventas + dividendos extraídos de un PDF tipo 1 (stocks/ETFs).

    `data` = [purchase_sales_rows, dividend_rows] tal como devuelve
    `extract_stocks_etf_1`.
    """
    purchase_sales, dividends_rows = data[0], data[1]

    symbols_needed = {row[2] for row in purchase_sales} | {row[2] for row in dividends_rows}
    if symbols_needed:
        result = await db.execute(
            select(Asset.symbol, Asset.id).where(
                Asset.symbol.in_(symbols_needed),
                Asset.kind.in_([AssetKind.stock, AssetKind.etf]),
            )
        )
        assets = {row.symbol: row.id for row in result.all()}
    else:
        assets = {}

    tx_objs: list[Transaction] = []
    div_objs: list[Dividend] = []
    errors: list[str] = []

    for row in purchase_sales:
        symbol = row[2]
        asset_id = assets.get(symbol)
        if not asset_id:
            errors.append(symbol)
            continue

        bought = row[5]
        tx_date = datetime.strptime(row[0], "%Y-%m-%d").date()
        tx_objs.append(
            Transaction(
                account_id=account_id,
                asset_id=asset_id,
                kind=TransactionKind.buy if bought > 0 else TransactionKind.sell,
                quantity=Decimal(str(row[5] if bought > 0 else row[7])),
                price=Decimal(str(row[4] if bought > 0 else row[6])),
                fee=Decimal("0"),
                executed_at=datetime.combine(tx_date, datetime.min.time()),
                date_=tx_date,
            )
        )

    for row in dividends_rows:
        symbol = row[2]
        asset_id = assets.get(symbol)
        if not asset_id:
            errors.append(symbol)
            continue
        div_objs.append(
            Dividend(
                account_id=account_id,
                asset_id=asset_id,
                date=datetime.strptime(row[0], "%Y-%m-%d").date(),
                gross_amount=Decimal(str(row[4])),
                tax_amount=Decimal(str(row[5])),
                net_amount=Decimal(str(row[6])),
            )
        )

    db.add_all(tx_objs)
    db.add_all(div_objs)
    await db.commit()

    return {
        "compras_ventas_guardadas": len(tx_objs),
        "dividendos_guardados": len(div_objs),
        "errores_activos_faltantes": errors,
    }


async def save_mutual_funds(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: list,
    account_id: uuid.UUID,
) -> dict:
    """Persiste aportes/rescates de fondos mutuos (Fintual).

    Asume que el catálogo `asset` para `kind='fund'` guarda:
      - `name`   = nombre del fondo (e.g. "Risky Norris")
      - `symbol` = identificador de la serie (e.g. "APV")
    """
    result = await db.execute(
        select(Asset.name, Asset.symbol, Asset.id).where(Asset.kind == AssetKind.fund)
    )
    assets = {(row.name, row.symbol): row.id for row in result.all()}

    tx_objs: list[Transaction] = []
    errors: list[str] = []

    for row in data:
        name = row[2]
        series = row[3]
        contributions = row[4]
        withdrawals = row[5]
        contributions_cpl = row[6]
        withdrawals_cpl = row[7]

        asset_id = assets.get((name, series))
        if not asset_id:
            errors.append(f"{name} - {series}")
            continue

        tx_date = datetime.strptime(row[0], "%d/%m/%Y").date()
        is_buy = contributions > 0
        tx_objs.append(
            Transaction(
                account_id=account_id,
                asset_id=asset_id,
                kind=TransactionKind.buy if is_buy else TransactionKind.sell,
                quantity=Decimal(str(contributions if is_buy else withdrawals)),
                price=Decimal(str(contributions_cpl if is_buy else withdrawals_cpl)),
                fee=Decimal("0"),
                executed_at=datetime.combine(tx_date, datetime.min.time()),
                date_=tx_date,
            )
        )

    db.add_all(tx_objs)
    await db.commit()

    return {
        "compras_ventas_guardadas": len(tx_objs),
        "errores_activos_faltantes": errors,
    }


async def stocks_etf_2(db: AsyncSession, user_id: uuid.UUID, data: list) -> dict:
    """Holdings de un PDF tipo 2 (estado de posición). Pendiente de cablear:
    requiere decidir si se materializa en `position` o solo se valida contra
    transacciones existentes."""
    return {"holdings_recibidos": len(data), "guardados": 0, "estado": "no implementado"}
