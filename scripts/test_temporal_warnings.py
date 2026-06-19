"""
Test de integración para warnings.py usando la base de datos real (Postgres).
Lee DATABASE_URL desde .env.

⚠️ ESTE SCRIPT BORRA TODOS LOS DATOS EXISTENTES DEL USUARIO DEFINIDO EN USER_ID
   (cuentas, posiciones, métricas, snapshots, alerts y preferencias) y los
   reemplaza por datos de prueba determinísticos. Los datos de prueba NO se
   borran al final, para poder inspeccionarlos en la DB.

   Usar solo con un usuario de TEST/DEV (user_3DvR9MbuQsBbtqZOn2WXhluGyYh).
"""

import asyncio
import uuid
import json
from datetime import date, timedelta
from dotenv import load_dotenv
import os

load_dotenv()

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

import re

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

# asyncpg no soporta sslmode en la URL, se pasa como connect_arg
ssl_match = re.search(r"[?&]sslmode=(\w+)", DATABASE_URL)
DATABASE_URL = re.sub(r"[?&]sslmode=\w+", "", DATABASE_URL).rstrip("?")
ssl_mode = ssl_match.group(1) if ssl_match else "require"

engine = create_async_engine(
    DATABASE_URL,
    connect_args={"ssl": ssl_mode} if ssl_mode != "disable" else {},
)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# --- Usuario de TEST (todos sus datos serán reemplazados) ---
USER_ID = "user_3DvR9MbuQsBbtqZOn2WXhluGyYh"

# IDs de prueba
ACCOUNT_ID      = uuid.uuid4()
SNAPSHOT_HOY    = uuid.uuid4()
SNAPSHOT_AYER   = uuid.uuid4()
ASSET_BTC_ID    = uuid.uuid4()
ASSET_ETH_ID    = uuid.uuid4()
POSITION_BTC_ID = uuid.uuid4()
POSITION_ETH_ID = uuid.uuid4()
TODAY           = date.today()
YESTERDAY       = TODAY - timedelta(days=1)

# Preferencias de test fijas y conocidas
PREF_PNL_ACCOUNT      = 0.10  # 10%
PREF_PNL_ASSET        = 0.08  # 8%
PREF_MAX_DD_PORTFOLIO = 0.07  # 7%
PREF_MAX_DD_ACCOUNT   = 0.14  # 14%
PREF_ASSET_WEIGHT     = 0.35  # 35%


async def wipe_user_data(db: AsyncSession):
    """Borra TODO lo existente del usuario: cuentas, posiciones, métricas,
    snapshots, alerts y preferencias. Los assets globales (BTC, ETH, etc.)
    no se tocan, salvo los que sean de prueba (BTC_TEST / ETH_TEST) de
    corridas anteriores que hayan quedado huérfanos."""

    # Position daily metrics (vía positions -> accounts del usuario)
    await db.execute(text("""
        DELETE FROM position_daily_metrics
        WHERE position_id IN (
            SELECT p.id FROM positions p
            JOIN accounts a ON a.id = p.account_id
            WHERE a.user_id = :u
        )
    """), {"u": USER_ID})

    # Account daily metrics
    await db.execute(text("""
        DELETE FROM account_daily_metrics
        WHERE account_id IN (
            SELECT id FROM accounts WHERE user_id = :u
        )
    """), {"u": USER_ID})

    # Positions
    await db.execute(text("""
        DELETE FROM positions
        WHERE account_id IN (
            SELECT id FROM accounts WHERE user_id = :u
        )
    """), {"u": USER_ID})

    # Portfolio daily metrics (vía snapshots del usuario)
    await db.execute(text("""
        DELETE FROM portfolio_daily_metrics
        WHERE portfolio_id IN (
            SELECT id FROM portfolio_snapshots WHERE user_id = :u
        )
    """), {"u": USER_ID})

    # Portfolio snapshots
    await db.execute(text("DELETE FROM portfolio_snapshots WHERE user_id = :u"), {"u": USER_ID})

    # Accounts
    await db.execute(text("DELETE FROM accounts WHERE user_id = :u"), {"u": USER_ID})

    # Alerts del usuario
    await db.execute(text("DELETE FROM alerts WHERE user_id = :u"), {"u": USER_ID})

    # User preferences (las reinsertamos con valores fijos)
    await db.execute(text("DELETE FROM user_preferences WHERE user_id = :u"), {"u": USER_ID})

    # Limpieza de posibles assets/precios huérfanos de corridas anteriores
    await db.execute(text("""
        DELETE FROM asset_prices
        WHERE asset_id IN (
            SELECT id FROM assets WHERE symbol IN ('BTC_TEST', 'ETH_TEST')
        )
    """))
    await db.execute(text("DELETE FROM assets WHERE symbol IN ('BTC_TEST', 'ETH_TEST')"))

    await db.commit()
    print("🧹 Datos previos del usuario eliminados")


async def insert_test_data(db: AsyncSession):
    # Account
    await db.execute(text("""
        INSERT INTO accounts (id, user_id, name, currency, created_at)
        VALUES (:id, :user_id, :name, 'USD', now())
    """), {"id": ACCOUNT_ID, "user_id": USER_ID, "name": "Cuenta Test"})

    # User preferences fijas
    await db.execute(text("""
        INSERT INTO user_preferences (id, user_id, pnl_percentage_account_daily, pnl_percentage_asset_daily,
            max_drawdown_portfolio_daily, max_drawdown_account_daily, asset_weight_weekly)
        VALUES (:id, :user_id, :pnl_acc, :pnl_asset, :dd_port, :dd_acc, :weight)
    """), {
        "id": uuid.uuid4(),
        "user_id": USER_ID,
        "pnl_acc": PREF_PNL_ACCOUNT,
        "pnl_asset": PREF_PNL_ASSET,
        "dd_port": PREF_MAX_DD_PORTFOLIO,
        "dd_acc": PREF_MAX_DD_ACCOUNT,
        "weight": PREF_ASSET_WEIGHT,
    })

    # Assets
    await db.execute(text("""
        INSERT INTO assets (id, symbol, name, kind, created_at)
        VALUES (:id, :symbol, :name, 'stock', now())
    """), {"id": ASSET_BTC_ID, "symbol": "BTC_TEST", "name": "Bitcoin Test"})

    await db.execute(text("""
        INSERT INTO assets (id, symbol, name, kind, created_at)
        VALUES (:id, :symbol, :name, 'stock', now())
    """), {"id": ASSET_ETH_ID, "symbol": "ETH_TEST", "name": "Ethereum Test"})

    # Asset prices
    # BTC: subió de 60000 -> 66000 (15% diario, supera el 8% de pref_pnl_asset)
    await db.execute(text("""
        INSERT INTO asset_prices (asset_id, date, close, currency)
        VALUES (:asset_id, :date, :close, 'USD')
    """), {"asset_id": ASSET_BTC_ID, "date": YESTERDAY, "close": 60000})
    await db.execute(text("""
        INSERT INTO asset_prices (asset_id, date, close, currency)
        VALUES (:asset_id, :date, :close, 'USD')
    """), {"asset_id": ASSET_BTC_ID, "date": TODAY, "close": 66000})

    # ETH: se mantuvo en 3000
    await db.execute(text("""
        INSERT INTO asset_prices (asset_id, date, close, currency)
        VALUES (:asset_id, :date, :close, 'USD')
    """), {"asset_id": ASSET_ETH_ID, "date": YESTERDAY, "close": 3000})
    await db.execute(text("""
        INSERT INTO asset_prices (asset_id, date, close, currency)
        VALUES (:asset_id, :date, :close, 'USD')
    """), {"asset_id": ASSET_ETH_ID, "date": TODAY, "close": 3000})

    # Portfolio snapshots
    # Ayer: total_value=10000
    await db.execute(text("""
        INSERT INTO portfolio_snapshots (id, user_id, date, total_value, breakdown_by_account)
        VALUES (:id, :user_id, :date, :total_value, :breakdown)
    """), {
        "id": SNAPSHOT_AYER,
        "user_id": USER_ID,
        "date": YESTERDAY,
        "total_value": 10000,
        "breakdown": json.dumps({str(ACCOUNT_ID): 10000}),
    })

    # Hoy: total_value=12600
    await db.execute(text("""
        INSERT INTO portfolio_snapshots (id, user_id, date, total_value, breakdown_by_account)
        VALUES (:id, :user_id, :date, :total_value, :breakdown)
    """), {
        "id": SNAPSHOT_HOY,
        "user_id": USER_ID,
        "date": TODAY,
        "total_value": 12600,
        "breakdown": json.dumps({str(ACCOUNT_ID): 12600}),
    })

    # Account daily metrics: pnl=1500 (16.7% de 9000 > 10%), drawdown=20% > 14%
    await db.execute(text("""
        INSERT INTO account_daily_metrics (id, account_id, date, pnl, max_drawdown)
        VALUES (:id, :account_id, :date, :pnl, :max_drawdown)
    """), {"id": uuid.uuid4(), "account_id": ACCOUNT_ID, "date": TODAY, "pnl": 1500, "max_drawdown": 0.20})

    # Portfolio daily metrics: max_drawdown=10% > 7%
    await db.execute(text("""
        INSERT INTO portfolio_daily_metrics (id, portfolio_id, date, pnl, max_drawdown)
        VALUES (:id, :portfolio_id, :date, :pnl, :max_drawdown)
    """), {"id": uuid.uuid4(), "portfolio_id": SNAPSHOT_HOY, "date": TODAY, "pnl": 80, "max_drawdown": 0.10})

    # Positions
    await db.execute(text("""
        INSERT INTO positions (id, account_id, asset_id, quantity)
        VALUES (:id, :account_id, :asset_id, :quantity)
    """), {"id": POSITION_BTC_ID, "account_id": ACCOUNT_ID, "asset_id": ASSET_BTC_ID, "quantity": 0.1})
    await db.execute(text("""
        INSERT INTO positions (id, account_id, asset_id, quantity)
        VALUES (:id, :account_id, :asset_id, :quantity)
    """), {"id": POSITION_ETH_ID, "account_id": ACCOUNT_ID, "asset_id": ASSET_ETH_ID, "quantity": 2.0})

    # Position daily metrics (fecha = hoy)
    # BTC: pnl=900, valor_ayer=0.1*60000=6000 -> pnl_pct=15% > 8% -> warning
    # ETH: pnl=120, valor_ayer=2.0*3000=6000  -> pnl_pct=2%  < 8% -> sin warning
    await db.execute(text("""
        INSERT INTO position_daily_metrics (id, position_id, date, pnl)
        VALUES (:id, :position_id, :date, :pnl)
    """), {"id": uuid.uuid4(), "position_id": POSITION_BTC_ID, "date": TODAY, "pnl": 900})
    await db.execute(text("""
        INSERT INTO position_daily_metrics (id, position_id, date, pnl)
        VALUES (:id, :position_id, :date, :pnl)
    """), {"id": uuid.uuid4(), "position_id": POSITION_ETH_ID, "date": TODAY, "pnl": 120})

    await db.commit()
    print("✅ Datos de prueba insertados (preferencias: "
          f"pnl_acc={PREF_PNL_ACCOUNT}, pnl_asset={PREF_PNL_ASSET}, "
          f"dd_port={PREF_MAX_DD_PORTFOLIO}, dd_acc={PREF_MAX_DD_ACCOUNT}, "
          f"weight={PREF_ASSET_WEIGHT})")


async def main():
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    import warnings_module as wm

    async with AsyncSessionLocal() as db:
        print(f"👤 Usuario de test: {USER_ID}")

        await wipe_user_data(db)
        await insert_test_data(db)

        print("\n🚀 Corriendo warnings...\n")
        result = await wm.warnings(db, USER_ID, send_mail=False)

        print("Warnings encontradas:")
        for w in result:
            print(" ", w)

        print(f"\nTotal: {len(result)}")
        found_types = set(w[0] for w in result)
        print("Tipos encontrados:", found_types)

        expected_types = {"P&L account", "max_drawdown", "P&L asset", "asset_weight"}
        print("Esperados:        ", expected_types)

        missing = expected_types - found_types
        extra   = found_types - expected_types
        if not missing and not extra:
            print("\n✅ Test pasado")
        else:
            if missing:
                print(f"\n❌ Faltan: {missing}")
            if extra:
                print(f"⚠️  Extras inesperados: {extra}")

        print("\nℹ️  Los datos de prueba quedaron en la base de datos (no se borraron).")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())