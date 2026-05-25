"""End-to-end smoke test against the live DB without going through Clerk.
Runs the same code paths the routers use (repositories), to verify the data
model works.

Usage:
    python -m scripts.smoke_test
"""
import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal

from app.core.db import SessionLocal
from app.models.asset import AssetKind
from app.models.transaction import TransactionKind
from app.repositories import (
    account_repo,
    asset_price_repo,
    asset_repo,
    position_repo,
    transaction_repo,
    user_repo,
)
from app.schemas.account import AccountCreate
from app.schemas.asset import AssetCreate
from app.schemas.asset_price import AssetPriceCreate
from app.schemas.transaction import TransactionCreate


async def main():
    async with SessionLocal() as db:
        # Two users to validate isolation
        u1 = await user_repo.get_or_create_by_clerk_id(db, "clerk_user_1", "u1@test.io")
        u2 = await user_repo.get_or_create_by_clerk_id(db, "clerk_user_2", "u2@test.io")
        print(f"users: u1={u1.clerk_id} u2={u2.clerk_id}")

        # Asset catalog (global)
        spy = await asset_repo.get_by_symbol(db, "SPY")
        if spy is None:
            spy = await asset_repo.create(
                db,
                AssetCreate(symbol="SPY", name="SPDR S&P 500", kind=AssetKind.etf, currency="USD"),
            )
        print(f"asset SPY: {spy.id}")

        # Price upsert
        await asset_price_repo.upsert(
            db,
            spy.id,
            AssetPriceCreate(date=date(2026, 4, 30), close=Decimal("445.30"), currency="USD", source="manual"),
        )

        # Account for u1
        acc1 = await account_repo.create(
            db, u1.clerk_id, AccountCreate(name="Fintual USD", broker="Fintual", currency="USD")
        )
        # Account for u2
        acc2 = await account_repo.create(
            db, u2.clerk_id, AccountCreate(name="IBKR", broker="IBKR", currency="USD")
        )

        # Buy from u1
        await transaction_repo.create_for_user(
            db,
            u1.clerk_id,
            TransactionCreate(
                account_id=acc1.id,
                asset_id=spy.id,
                kind=TransactionKind.buy,
                quantity=Decimal("25"),
                price=Decimal("420.00"),
                fee=Decimal("0.50"),
                executed_at=datetime(2026, 3, 1, 15, 0, tzinfo=timezone.utc),
            ),
        )

        # Cross-user attempt: u2 tries to add a tx into acc1 (not theirs)
        bad = await transaction_repo.create_for_user(
            db,
            u2.clerk_id,
            TransactionCreate(
                account_id=acc1.id,
                asset_id=spy.id,
                kind=TransactionKind.buy,
                quantity=Decimal("999"),
                price=Decimal("1"),
                executed_at=datetime.now(tz=timezone.utc),
            ),
        )
        assert bad is None, "isolation broken: u2 wrote into u1 account"
        print("isolation enforced: u2 cannot post tx on u1 account")

        # Listings per user
        accs_u1 = await account_repo.list_for_user(db, u1.clerk_id)
        accs_u2 = await account_repo.list_for_user(db, u2.clerk_id)
        assert {a.id for a in accs_u1} == {acc1.id}
        assert {a.id for a in accs_u2} == {acc2.id}
        print(f"u1 accounts={len(accs_u1)}  u2 accounts={len(accs_u2)}")

        # Positions for u1
        positions = await position_repo.list_for_user(db, u1.clerk_id)
        for p in positions:
            print(
                f"position: symbol={p['symbol']} qty={p['quantity']} "
                f"avg={p['avg_cost']} last={p['last_price']} "
                f"mv={p['market_value']} pnl={p['unrealized_pnl']}"
            )
        assert len(positions) == 1
        p = positions[0]
        assert p["symbol"] == "SPY"
        assert Decimal(p["quantity"]) == Decimal("25")
        assert Decimal(p["avg_cost"]) == Decimal("420")
        assert Decimal(p["last_price"]) == Decimal("445.30000000")
        assert Decimal(p["market_value"]) == Decimal("11132.50000000")

        # Positions for u2 must be empty
        positions_u2 = await position_repo.list_for_user(db, u2.clerk_id)
        assert positions_u2 == []
        print("u2 positions empty as expected")

        print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
