"""Job batch: reconstruye portfolio_snapshots + positions para cada user.

Itera sobre todos los usuarios con transactions y, para cada uno:
  1. Computa la serie temporal de portafolio en memoria
  2. DELETE WHERE user_id = X + INSERT batch (idempotente, scoped al user)

Uso:
    DATABASE_URL='postgresql+asyncpg://...' python -m scripts_ghactions.portfolio_reconstruction

Gatillado por:
    - GH Action diaria (06:00 UTC, después de sync_stock_prices)
    - workflow_dispatch manual
    - python -m scripts_ghactions.portfolio_reconstruction localmente

⚠️ NUNCA hace DELETE sin WHERE. Si falla en un user, sigue con el resto.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import traceback

# Permitir invocar el módulo desde la raíz del repo
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import SessionLocal
from app.repositories import portfolio_repo


async def main() -> int:
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║  PORTFOLIO RECONSTRUCTION                                        ║")
    print("╚══════════════════════════════════════════════════════════════════╝")

    db_url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URL_DEV", "")
    print(f"  DB: {db_url[:60]}{'...' if len(db_url) > 60 else ''}")

    async with SessionLocal() as db:
        users = await portfolio_repo.list_users_with_transactions(db)
    print(f"  {len(users)} usuarios con transactions a reconstruir")
    print()

    ok = 0
    fail = 0
    for i, user in enumerate(users, 1):
        t0 = time.time()
        # Normalizar: si viene como string, envolverlo en objeto con .clerk_id
        if isinstance(user, str):
            class _U:
                def __init__(self, cid): self.clerk_id = cid
            user = _U(user)
        try:
            async with SessionLocal() as db:
                snaps, pos = await portfolio_repo.compute_user_series(db, user.clerk_id)
                n_snaps = await portfolio_repo.replace_snapshots(db, user.clerk_id, snaps)
                n_pos = await portfolio_repo.replace_positions(db, user, pos)
            elapsed = time.time() - t0
            print(f"  [{i}/{len(users)}] {user.clerk_id}: {n_snaps} snapshots, "
                  f"{n_pos} positions ({elapsed:.2f}s)")
            ok += 1
        except Exception as exc:
            fail += 1
            print(f"  [{i}/{len(users)}] {user.clerk_id}: ❌ {exc}")
            traceback.print_exc()

    print()
    print(f"  RESULTADO: {ok} OK, {fail} FAIL")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
