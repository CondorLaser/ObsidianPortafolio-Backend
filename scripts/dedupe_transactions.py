"""Limpieza one-shot: elimina transacciones y dividendos DUPLICADOS exactos,
producto de re-subir el mismo PDF (save_mutual_funds/stocks_etf_1 hacen
`add_all`, que agrega en vez de reemplazar).

Criterio de duplicado exacto:
  - transactions: (account_id, asset_id, executed_at, quantity, price, kind)
  - dividends:    (account_id, asset_id, date, gross_amount, tax_amount, net_amount)
Conserva 1 fila por grupo (la de menor id) y borra el resto.

⚠️ Borra datos. Dry-run por defecto; --apply para escribir. Hacer un branch /
   point-in-time en Neon antes de --apply.

Uso:
    APP_ENV=prod DATABASE_URL='...neon...' python -m scripts.dedupe_transactions
    APP_ENV=prod DATABASE_URL='...neon...' python -m scripts.dedupe_transactions --apply
    ... --apply --clerk-id user_xxx     # acotar a un usuario
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402

# (tabla, columnas que definen "duplicado exacto")
GROUPS = {
    "transactions": "account_id, asset_id, executed_at, quantity, price, kind",
    "dividends": "account_id, asset_id, date, gross_amount, tax_amount, net_amount",
}


def _scope(clerk_id: str | None) -> tuple[str, dict]:
    if not clerk_id:
        return "", {}
    return (
        " AND account_id IN (SELECT id FROM accounts WHERE user_id = :clerk_id)",
        {"clerk_id": clerk_id},
    )


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="aplica los DELETE (default: dry-run)")
    ap.add_argument("--clerk-id", default=None, help="acotar a un usuario")
    args = ap.parse_args()

    print(f"  modo: {'APPLY (borra)' if args.apply else 'DRY-RUN (no borra)'}")
    if args.clerk_id:
        print(f"  scope: clerk_id={args.clerk_id}")
    print()

    scope_sql, params = _scope(args.clerk_id)
    total_deleted = 0

    async with SessionLocal() as db:
        for table, cols in GROUPS.items():
            # filas sobrantes = total - distintos por grupo
            dup_sql = (
                f"SELECT id FROM (SELECT id, row_number() OVER "
                f"(PARTITION BY {cols} ORDER BY id) AS rn FROM {table} "
                f"WHERE TRUE{scope_sql}) t WHERE rn > 1"
            )
            n = (await db.execute(
                text(f"SELECT count(*) FROM ({dup_sql}) x"), params
            )).scalar_one()
            total = (await db.execute(
                text(f"SELECT count(*) FROM {table} WHERE TRUE{scope_sql}"), params
            )).scalar_one()
            print(f"  {table:14} total={total:>5}  duplicados a borrar={n:>5}  -> quedan {total - n}")

            if args.apply and n:
                res = await db.execute(
                    text(f"DELETE FROM {table} WHERE id IN ({dup_sql})"), params
                )
                total_deleted += res.rowcount

        if args.apply:
            await db.commit()
            print(f"\n  ✅ {total_deleted} filas duplicadas borradas.")
            print("  Ahora reconstruye: python -m scripts_ghactions.portfolio_reconstruction")
        else:
            print("\n  DRY-RUN: no se borró nada. Re-corre con --apply para aplicar.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
