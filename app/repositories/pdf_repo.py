import uuid
from app.models.asset import Asset
from app.models.transaction import Transaction
from app.models.dividend import Dividend
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from sqlalchemy import select

async def stocks_etf_1(db: AsyncSession, user_id: uuid.UUID, data: list, account_id: uuid.UUID):

    result = await db.execute( #request para conseguir asset_id por symbol
        select(Asset.symbol, Asset.id)
        .where(
            Asset.symbol == symbol,
            Asset.kind.in_(["stock", "etf"])
        )
    ) 

    assets = {row.symbol: row.id for row in result.all()}

    purcharse_sales = data[0]  # lista de compras/ventas
    dividends = data[1]        # lista de dividendos
    purcharse_sales_objs = []
    dividends_objs =[]
    errors = []

    for row in purcharse_sales:
        # ver si el asset existe, si no existe skipear row
        symbol = row[2]
        asset = assets.get(symbol)
        if not asset:
            errors.append(symbol)
            continue

        acciones_compradas = row[5]

        obj = Transaction(
            account_id=account_id,
            asset_id=asset,
            date_=datetime.strptime(row[0], "%Y-%m-%d").date(),
            executed_at=datetime.strptime(row[0], "%Y-%m-%d"),
            kind="buy" if acciones_compradas > 0 else "sell",
            quantity=row[5] if acciones_compradas > 0 else row[7],
            price=row[4] if acciones_compradas > 0 else row[6],
            fee=0,
        )
        purcharse_sales_objs.append(obj)

    #dividendos_objs = []
    for row in dividends:
        symbol = row[2]
        asset = assets.get(symbol)
        if not asset:
            errors.append(symbol)
            continue

        obj = Dividend(
            asset_id=asset,
            account_id=account_id,
            date=datetime.strptime(row[0], "%Y-%m-%d").date(),
            gross_amount=row[4],
            tax_amount=row[5],
            net_amount=row[6],
        )
        dividends_objs.append(obj)

    db.add_all(purcharse_sales_objs)
    db.add_all(dividends_objs)

    await db.commit()

    return {
        "compras_ventas_guardadas": len(purcharse_sales_objs),
        "dividendos_guardados": len(dividends_objs),
        "Errores (activos faltantes)" : errors
    }

async def save_mutual_funds(db: AsyncSession, user_id: uuid.UUID, data: dict, account_id: uuid.UUID):

    purcharse_sales_objs = []
    errors = []

    result = await db.execute(
        select(Asset.name, Asset.symbol, Asset.id)
        .where(
            Asset.kind == "fund"
            )
    )

    assets = {(row.name, row.symbol): row.id 
    for row in result.all()
    }   

    for row in data:
        date = row[0] #rows.append([fecha,nombre_inversion, nombre_fondo, serie_fondo,  aportes, rescate,  aportes_cpl, rescate_cpl ])
        name = row[2]
        series = row[3]
        contributions = row[4]
        withdrawals = row[5]
        contributions_cpl = row[6]
        withdrawals_cpl = row[7]


        asset = assets.get((name, series))
        if not asset:
            errors.append(f"{name} - {series}")
            continue
        
        
        obj = Transaction(
            account_id=account_id,
            asset_id=asset,
            date_=datetime.strptime(row[0], "%d/%m/%Y").date(),
            executed_at=datetime.strptime(row[0], "%d/%m/%Y"),
            kind="buy" if contributions > 0 else "sell",
            quantity=contributions if contributions > 0 else withdrawals,
            price=contributions_cpl if contributions > 0 else withdrawals_cpl,
            fee=0,
        )
        purcharse_sales_objs.append(obj)


    db.add_all(purcharse_sales_objs)

    await db.commit()

    return {
        "compras_ventas_guardadas": len(purcharse_sales_objs),
        "Errores (activos faltantes)" : errors
    }


async def stocks_etf_2(db: AsyncSession, user_id: uuid.UUID, data: dict):
    pass