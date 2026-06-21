from __future__ import annotations

import asyncio
import os
import sys
import time
import json
import traceback

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from app.core.db import SessionLocal
from app.repositories import portfolio_repo
from app.routers.portfolio import calculate_portfolio_daily_metrics, calculate_portfolio_monthly_metrics

from sqlalchemy import text
import uuid


async def main() -> int:
    print("╔══════════════════════════════════════╗")
    print("║ PORTFOLIO METRICS                   ║")
    print("╚══════════════════════════════════════╝")

    async with SessionLocal() as db:
        clerk_ids = await portfolio_repo.list_users_with_transactions(db)

    ok = 0
    fail = 0

    for i, clerk_id in enumerate(clerk_ids, 1):
        t0 = time.time()

        try:
            async with SessionLocal() as db:

                result = await db.execute(
                    text("""
                        SELECT *
                        FROM portfolio_snapshots
                        WHERE user_id = :user_id
                        ORDER BY date ASC
                    """),
                    {"user_id": clerk_id},
                )

                snapshots = result.mappings().all()

                if not snapshots:
                    continue

                daily = calculate_portfolio_daily_metrics(snapshots)
                monthly = calculate_portfolio_monthly_metrics(snapshots)

                await db.execute(
                    text("""
                        INSERT INTO portfolio_daily_metrics
                        (
                            id,
                            user_id,
                            date,
                            pnl,
                            max_drawdown,
                            volatility
                        )
                        VALUES
                        (
                            :id,
                            :user_id,
                            :date,
                            :pnl,
                            :max_drawdown,
                            :volatility
                        )
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "user_id": clerk_id,
                        "date": daily["date"],
                        "pnl": json.dumps(daily["pnl"]),
                        "max_drawdown": json.dumps(daily["max_drawdown"]),
                        "volatility": json.dumps(daily["volatility"]),
                    },
                )

                await db.execute(
                    text("""
                        INSERT INTO portfolio_monthly_metrics
                        (
                            id,
                            user_id,
                            date,
                            twr,
                            var
                        )
                        VALUES
                        (
                            :id,
                            :user_id,
                            :date,
                            :twr,
                            :var
                        )
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "user_id": clerk_id,
                        "date": monthly["date"],
                        "twr": json.dumps(monthly["twr"]),
                        "var": json.dumps(monthly["var"]),
                    },
                )

                await db.commit()

            elapsed = time.time() - t0

            print(
                f"[{i}/{len(clerk_ids)}] "
                f"{clerk_id}: OK "
                f"({elapsed:.2f}s)"
            )

            ok += 1

        except Exception as exc:
            fail += 1
            print(
                f"[{i}/{len(clerk_ids)}] "
                f"{clerk_id}: ❌ {exc}"
            )
            traceback.print_exc()

    print()
    print(f"RESULTADO: {ok} OK, {fail} FAIL")

    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))