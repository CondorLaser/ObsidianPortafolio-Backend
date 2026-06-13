"""Fix one-shot: corrige el `price` de transacciones de fondos mutuos ya
ingestadas con el bug (price = monto en pesos, en vez de valor cuota).

Contexto:
  `save_mutual_funds` guardaba `quantity = nº de cuotas` (correcto) y
  `price = monto en pesos` (incorrecto). El valor cuota correcto se deriva
  del propio dato guardado:

      valor_cuota = monto_pesos / cuotas = price_actual / quantity_actual

  Así que el fix in-place es:  price := price / quantity
  (solo assets kind='fund', quantity > 0).

⚠️ NO es idempotente: correrlo dos veces divide dos veces. Está pensado para
   correrse UNA sola vez sobre la data vieja (toda buggy). Hazlo ANTES de
   ingestar fondos nuevos con el código ya corregido.

Uso:
    # 1) Dry-run (NO escribe nada, solo muestra qué haría):
    APP_ENV=prod DATABASE_URL='postgresql+asyncpg://...neon...' \\
        python -m scripts.fix_fund_prices_inplace

    # 2) Aplicar de verdad:
    APP_ENV=prod DATABASE_URL='postgresql+asyncpg://...neon...' \\
        python -m scripts.fix_fund_prices_inplace --apply

    # Acotar a un usuario (opcional):
    ... --apply --clerk-id user_xxx

Después de aplicar, reconstruye snapshots + positions:
    APP_ENV=prod DATABASE_URL='...neon...' \\
        python -m scripts_ghactions.portfolio_reconstruction
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402

# Rango plausible de un valor cuota Fintual (CLP). Fuera de esto, se avisa.
VALOR_CUOTA_MIN = 1.0
VALOR_CUOTA_MAX = 100_000.0


def _scope_clause(clerk_id: str | None) -> tuple[str, dict]:
    """WHERE extra para acotar a un usuario (vía accounts.user_id)."""
    if not clerk_id:
        return "", {}
    return (
        " AND t.account_id IN (SELECT id FROM accounts WHERE user_id = :clerk_id)",
        {"clerk_id": clerk_id},
    )


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="aplica el UPDATE (default: dry-run)")
    ap.add_argument("--clerk-id", default=None, help="acotar a un usuario")
    args = ap.parse_args()

    db_url = os.environ.get("DATABASE_URL", "")
    print(f"  DB: {db_url[:55]}{'...' if len(db_url) > 55 else ''}")
    print(f"  modo: {'APPLY (escribe)' if args.apply else 'DRY-RUN (no escribe)'}")
    if args.clerk_id:
        print(f"  scope: clerk_id={args.clerk_id}")
    print()

    scope_sql, scope_params = _scope_clause(args.clerk_id)

    base_where = (
        "FROM transactions t "
        "JOIN assets a ON a.id = t.asset_id "
        "WHERE a.kind = 'fund' AND t.quantity > 0" + scope_sql
    )

    async with SessionLocal() as db:
        # Conteo de filas afectadas
        n = (await db.execute(text(f"SELECT count(*) {base_where}"), scope_params)).scalar_one()
        print(f"  transacciones de fondos a corregir: {n}")
        if n == 0:
            print("  nada que hacer.")
            return 0

        # Preview: muestra una muestra con price actual -> valor cuota derivado
        rows = (await db.execute(
            text(
                "SELECT a.name, a.symbol, t.quantity, t.price, "
                "(t.price / t.quantity) AS valor_cuota "
                f"{base_where} ORDER BY t.executed_at DESC LIMIT 8"
            ),
            scope_params,
        )).all()
        print(f"\n  {'fondo':24}{'serie':6}{'cuotas':>12}{'price_actual':>16}{'-> valor_cuota':>16}")
        outliers = 0
        for name, symbol, qty, price, vc in rows:
            flag = ""
            if not (VALOR_CUOTA_MIN <= float(vc) <= VALOR_CUOTA_MAX):
                flag = "  ⚠️ fuera de rango"
                outliers += 1
            print(f"  {str(name)[:24]:24}{str(symbol)[:6]:6}{float(qty):>12.4f}{float(price):>16,.2f}{float(vc):>16,.4f}{flag}")

        # Chequeo global de rango sobre TODAS las filas (no solo la muestra)
        bad = (await db.execute(
            text(
                "SELECT count(*) " + base_where +
                f" AND (t.price / t.quantity) NOT BETWEEN {VALOR_CUOTA_MIN} AND {VALOR_CUOTA_MAX}"
            ),
            scope_params,
        )).scalar_one()
        if bad:
            print(f"\n  ⚠️ {bad} filas darían un valor_cuota fuera de [{VALOR_CUOTA_MIN}, {VALOR_CUOTA_MAX}]."
                  f" Revísalas antes de aplicar.")

        if not args.apply:
            print("\n  DRY-RUN: no se escribió nada. Re-corre con --apply para aplicar.")
            return 0

        # Aplicar
        result = await db.execute(
            text(
                "UPDATE transactions t SET price = t.price / t.quantity "
                "FROM assets a "
                "WHERE a.id = t.asset_id AND a.kind = 'fund' AND t.quantity > 0" + scope_sql
            ),
            scope_params,
        )
        await db.commit()
        print(f"\n  ✅ {result.rowcount} transacciones de fondos corregidas (price = valor cuota).")
        print("  Ahora reconstruye: python -m scripts_ghactions.portfolio_reconstruction")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
