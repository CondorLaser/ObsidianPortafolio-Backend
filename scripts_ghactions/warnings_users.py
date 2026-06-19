"""Job: Ejecuta las comprobaciones de `warnings` y envía mails si procede.

Uso:
    DATABASE_URL='postgresql+asyncpg://...' python -m scripts_ghactions.warnings

Se itera sobre los `clerk_id` de usuarios con transacciones y se invoca
la función `warnings` de `scripts/warnings_module.py` con `send_mail=True`.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import traceback

# Permitir invocar el módulo desde la raíz del repo y desde /scripts
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from app.core.db import SessionLocal
from app.repositories import portfolio_repo

import warnings_module as wm


async def main() -> int:
    print("╔════════════════════════════════════════════════╗")
    print("║  WARNINGS JOB (envío de mails si aplica)       ║")
    print("╚════════════════════════════════════════════════╝")

    db_url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URL_DEV", "")
    print(f"  DB: {db_url[:60]}{'...' if len(db_url) > 60 else ''}")

    async with SessionLocal() as db:
        clerk_ids = await portfolio_repo.list_users_with_transactions(db)

    print(f"  {len(clerk_ids)} usuarios candidatos para evaluar warnings")
    print()

    ok = 0
    fail = 0
    for i, clerk_id in enumerate(clerk_ids, 1):
        t0 = time.time()
        try:
            async with SessionLocal() as db:
                found = await wm.warnings(db, clerk_id, send_mail=True)
            elapsed = time.time() - t0
            print(f"  [{i}/{len(clerk_ids)}] {clerk_id}: {len(found)} warnings ({elapsed:.2f}s)")
            ok += 1
        except Exception as exc:
            fail += 1
            print(f"  [{i}/{len(clerk_ids)}] {clerk_id}: ❌ {exc}")
            traceback.print_exc()

    print()
    print(f"  RESULTADO: {ok} OK, {fail} FAIL")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
