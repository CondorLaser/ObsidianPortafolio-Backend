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


# ── Idempotencia de la ingesta ───────────────────────────────────────────
# La ingesta de PDFs es append-only por naturaleza (Fintual entrega el historial
# completo). Re-subir el mismo PDF NO debe duplicar. Se filtran las filas cuya
# clave de negocio ya existe en la cuenta (o se repite dentro del mismo lote).
# Se usa `date_` (no `executed_at`) en la clave: `executed_at` vuelve tz-aware
# desde la BD y no matchearía con el naive que construimos al insertar.

def _tx_key(t: "Transaction") -> tuple:
    return (t.asset_id, t.date_, t.quantity, t.price, t.kind)


def _div_key(d: "Dividend") -> tuple:
    return (d.asset_id, d.date, d.gross_amount, d.tax_amount, d.net_amount)


async def _existing_tx_keys(db: AsyncSession, account_id: uuid.UUID) -> set:
    rows = await db.execute(
        select(
            Transaction.asset_id, Transaction.date_,
            Transaction.quantity, Transaction.price, Transaction.kind,
        ).where(Transaction.account_id == account_id)
    )
    return {tuple(r) for r in rows.all()}


async def _existing_div_keys(db: AsyncSession, account_id: uuid.UUID) -> set:
    rows = await db.execute(
        select(
            Dividend.asset_id, Dividend.date,
            Dividend.gross_amount, Dividend.tax_amount, Dividend.net_amount,
        ).where(Dividend.account_id == account_id)
    )
    return {tuple(r) for r in rows.all()}


def _dedupe(objs: list, key_fn, seen: set) -> tuple[list, int]:
    """Filtra `objs` dejando solo los que no están en `seen` (mutándolo).
    Devuelve (nuevos, n_duplicados_omitidos)."""
    nuevos = []
    dups = 0
    for o in objs:
        k = key_fn(o)
        if k in seen:
            dups += 1
            continue
        seen.add(k)
        nuevos.append(o)
    return nuevos, dups


async def stocks_etf_1(
    db: AsyncSession,
    clerk_id: str,
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

    # Idempotencia: no re-insertar lo que ya existe en la cuenta.
    tx_new, tx_dups = _dedupe(tx_objs, _tx_key, await _existing_tx_keys(db, account_id))
    div_new, div_dups = _dedupe(div_objs, _div_key, await _existing_div_keys(db, account_id))
    db.add_all(tx_new)
    db.add_all(div_new)
    await db.commit()

    return {
        "compras_ventas_guardadas": len(tx_new),
        "dividendos_guardados": len(div_new),
        "duplicados_omitidos": tx_dups + div_dups,
        "errores_activos_faltantes": errors,
    }


async def save_mutual_funds(
    db: AsyncSession,
    clerk_id: str,
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
        # Fila de extract_mutual_funds:
        #   [fecha, nom_inv, nom_fondo, serie, aporte_cuotas, rescate_cuotas,
        #    valor_cuota, aporte_pesos, rescate_pesos]
        aporte_cuotas = row[4]
        rescate_cuotas = row[5]
        valor_cuota = row[6]

        asset_id = assets.get((name, series))
        if not asset_id:
            errors.append(f"{name} - {series}")
            continue

        tx_date = datetime.strptime(row[0], "%d/%m/%Y").date()
        is_buy = aporte_cuotas > 0
        # quantity = nº de cuotas (unidades); price = valor de la cuota (CLP).
        # Así quantity * price = monto aportado/rescatado en pesos.
        tx_objs.append(
            Transaction(
                account_id=account_id,
                asset_id=asset_id,
                kind=TransactionKind.buy if is_buy else TransactionKind.sell,
                quantity=Decimal(str(aporte_cuotas if is_buy else rescate_cuotas)),
                price=Decimal(str(valor_cuota)),
                fee=Decimal("0"),
                executed_at=datetime.combine(tx_date, datetime.min.time()),
                date_=tx_date,
            )
        )

    # Idempotencia: no re-insertar lo que ya existe en la cuenta.
    tx_new, tx_dups = _dedupe(tx_objs, _tx_key, await _existing_tx_keys(db, account_id))
    db.add_all(tx_new)
    await db.commit()

    return {
        "compras_ventas_guardadas": len(tx_new),
        "duplicados_omitidos": tx_dups,
        "errores_activos_faltantes": errors,
    }


async def stocks_etf_2(db: AsyncSession, clerk_id: str, data: list) -> dict:
    """Holdings de un PDF tipo 2 (estado de posición). Pendiente de cablear:
    requiere decidir si se materializa en `position` o solo se valida contra
    transacciones existentes."""
    return {"holdings_recibidos": len(data), "guardados": 0, "estado": "no implementado"}
