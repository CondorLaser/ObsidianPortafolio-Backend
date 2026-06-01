"""Reconstrucción de portafolio: time series de posiciones → portfolio_snapshots.

Algoritmo:
  1. Para cada usuario con transactions, traer todas sus tx ordenadas por
     executed_at (join con accounts).
  2. Para cada día D entre min(executed_at).date() y today():
       - Actualizar running quantity / invested por (account, asset) hasta D.
       - Obtener precio del asset en D con forward-fill (último close con date <= D).
       - position_value(D) = qty * precio.
  3. Sumar por (user, D) → total_value diario; insertar fila por D en
     portfolio_snapshots (DELETE WHERE user_id + INSERT — idempotente).
  4. Recomputar `positions` (latest state) y reemplazar para ese user.

Decisiones:
  - DELETE WHERE user_id = ? + INSERT en lugar de UPSERT (no hay UNIQUE
    constraint en Neon sobre user_id+date, evitamos drift de schema).
  - Forward-fill: si un asset no tiene precio para una fecha, uso el último
    close conocido <= D. Si NUNCA hubo precio, uso avg_cost como fallback
    (mejor que excluir la posición de la valuación).
  - dividends/fees/deposits/withdrawals NO cambian quantity (solo buy/sell).
  - total_invested = SUM(buy.qty * buy.price + buy.fee) acumulado hasta D.
  - unrealized_pnl = total_value - total_invested_de_qty_actual. Simplificación
    para el MVP: no tracking de FIFO/LIFO; usamos avg_cost_acumulado.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date as date_type, datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable

from sqlalchemy import delete, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.asset import Asset
from app.models.asset_price import AssetPrice
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.position import Position
from app.models.transaction import Transaction, TransactionKind
from app.models.user import Profile


ZERO = Decimal("0")


@dataclass
class _PairState:
    """Estado acumulado por par (account_id, asset_id)."""

    qty: Decimal = ZERO
    invested: Decimal = ZERO  # acumulado de qty*price+fee de buys
    realized_pnl: Decimal = ZERO  # acumulado al vender (sell.qty * (sell.price - avg_cost))
    total_dividends: Decimal = ZERO
    total_fees: Decimal = ZERO
    last_tx_at: datetime | None = None

    @property
    def avg_cost(self) -> Decimal | None:
        if self.qty > 0:
            # avg_cost ≈ invested / qty siempre que qty > 0
            return self.invested / self.qty if self.qty != 0 else None
        return None


async def compute_user_series(
    session: AsyncSession,
    clerk_id: str,
) -> tuple[list[dict], list[dict]]:
    """Devuelve (snapshots, positions_latest) sin tocar la DB.

    Calcula la serie temporal completa en memoria. Para un usuario típico (≤200
    tx, ≤20 assets, ≤2 años) son <800 días × Python ops; OK para batch nocturno.
    """
    # ── 1. Traer todas las txs del user + el currency de cada cuenta ──────
    tx_q = await session.execute(
        select(
            Transaction.id,
            Transaction.account_id,
            Transaction.asset_id,
            Transaction.kind,
            Transaction.quantity,
            Transaction.price,
            Transaction.fee,
            Transaction.executed_at,
            Account.currency.label("account_currency"),
            Account.name.label("account_name"),
        )
        .join(Account, Account.id == Transaction.account_id)
        .where(Account.user_id == clerk_id)
        .order_by(Transaction.executed_at.asc())
    )
    txs = tx_q.all()
    if not txs:
        return [], []

    # ── 2. Traer prices de los assets involucrados ────────────────────────
    asset_ids = {row.asset_id for row in txs}
    px_q = await session.execute(
        select(AssetPrice.asset_id, AssetPrice.date, AssetPrice.close)
        .where(AssetPrice.asset_id.in_(asset_ids))
        .order_by(AssetPrice.asset_id, AssetPrice.date.asc())
    )
    # asset_id -> [(date, close), ...] ordenado asc
    prices_by_asset: dict[uuid.UUID, list[tuple[date_type, Decimal]]] = defaultdict(list)
    for r in px_q:
        prices_by_asset[r.asset_id].append((r.date, r.close))

    def price_on_or_before(asset_id: uuid.UUID, d: date_type) -> Decimal | None:
        """Forward-fill: último close con date <= d, o None si no hay ninguno aún."""
        series = prices_by_asset.get(asset_id, [])
        # busqueda lineal hacia atrás (las series son cortas en general)
        last: Decimal | None = None
        for pd, pc in series:
            if pd <= d:
                last = pc
            else:
                break
        return last

    # ── 3. Iteración día por día ──────────────────────────────────────────
    pair_state: dict[tuple[uuid.UUID, uuid.UUID], _PairState] = defaultdict(_PairState)
    # account_id -> currency / name (para breakdown_by_account/currency)
    account_meta: dict[uuid.UUID, tuple[str, str]] = {}
    for row in txs:
        account_meta[row.account_id] = (row.account_currency, row.account_name)

    start_date = txs[0].executed_at.date()
    end_date = datetime.now(tz=timezone.utc).date()

    tx_idx = 0  # próximo tx a procesar
    snapshots: list[dict] = []

    cur_date = start_date
    while cur_date <= end_date:
        # ── consumir todas las txs cuyo executed_at.date() <= cur_date ────
        while tx_idx < len(txs) and txs[tx_idx].executed_at.date() <= cur_date:
            tx = txs[tx_idx]
            st = pair_state[(tx.account_id, tx.asset_id)]
            qty = tx.quantity or ZERO
            price = tx.price or ZERO
            fee = tx.fee or ZERO

            if tx.kind == TransactionKind.buy:
                st.qty += qty
                st.invested += qty * price + fee
                st.total_fees += fee
            elif tx.kind == TransactionKind.sell:
                # realized pnl al avg_cost actual
                avg = st.avg_cost or ZERO
                st.realized_pnl += qty * (price - avg)
                # reducir invested proporcionalmente
                if st.qty > 0:
                    st.invested -= avg * qty
                st.qty -= qty
                st.total_fees += fee
            elif tx.kind == TransactionKind.dividend:
                # qty del registro de dividend representa monto del dividendo
                # (el frontend / Eduardo modeló dividends con kind=dividend y
                # quantity = monto cash; no afecta posición)
                st.total_dividends += qty
            elif tx.kind == TransactionKind.fee:
                st.total_fees += fee or qty
            # deposit/withdrawal no afectan posiciones por asset
            st.last_tx_at = tx.executed_at
            tx_idx += 1

        # ── valuar todas las posiciones a cur_date ────────────────────────
        total_value = ZERO
        total_invested = ZERO
        per_currency: dict[str, Decimal] = defaultdict(lambda: ZERO)
        per_account: dict[str, Decimal] = defaultdict(lambda: ZERO)

        for (acc_id, ast_id), st in pair_state.items():
            if st.qty <= 0:
                # posición cerrada — no aporta a valor de mercado, pero invested
                # ya se descontó en el sell. Skip.
                continue
            px = price_on_or_before(ast_id, cur_date)
            # fallback: si no hay precio aún para esta fecha, usar avg_cost
            valuation_price = px if px is not None else (st.avg_cost or ZERO)
            mv = st.qty * valuation_price
            total_value += mv
            total_invested += st.invested
            currency = account_meta[acc_id][0]
            per_currency[currency] += mv
            per_account[str(acc_id)] += mv

        snapshots.append(
            {
                "user_id": clerk_id,
                "date": cur_date,
                "total_value": total_value,
                "total_invested": total_invested,
                "unrealized_pnl": total_value - total_invested,
                "realized_pnl": sum((s.realized_pnl for s in pair_state.values()), ZERO),
                "breakdown_by_currency": {k: float(v) for k, v in per_currency.items()},
                "breakdown_by_account": {k: float(v) for k, v in per_account.items()},
            }
        )

        cur_date += timedelta(days=1)

    # ── 4. Estado latest de positions ─────────────────────────────────────
    now = datetime.now(tz=timezone.utc)
    positions_latest = []
    for (acc_id, ast_id), st in pair_state.items():
        if st.qty == 0 and st.realized_pnl == 0 and st.total_dividends == 0:
            continue  # posición vacía sin historia
        positions_latest.append(
            {
                "account_id": acc_id,
                "asset_id": ast_id,
                "quantity": st.qty,
                "avg_cost": st.avg_cost,
                "realized_pnl": st.realized_pnl,
                "total_dividends": st.total_dividends,
                "total_fees": st.total_fees,
                "last_transaction_at": st.last_tx_at,
                "updated_at": now,
            }
        )

    return snapshots, positions_latest


async def replace_snapshots(
    session: AsyncSession, clerk_id: str, snapshots: list[dict]
) -> int:
    """DELETE WHERE user_id + INSERT. Idempotente, scoped al user."""
    await session.execute(
        delete(PortfolioSnapshot).where(PortfolioSnapshot.user_id == clerk_id)
    )
    if snapshots:
        # Inyectar id explícito (no hay server_default)
        rows = [{"id": uuid.uuid4(), **s} for s in snapshots]
        await session.execute(insert(PortfolioSnapshot), rows)
    await session.commit()
    return len(snapshots)


async def replace_positions(
    session: AsyncSession, clerk_id: str, positions: list[dict]
) -> int:
    """Reemplaza positions del user (DELETE las de sus accounts + INSERT)."""
    # accounts del user
    accs_q = await session.execute(
        select(Account.id).where(Account.user_id == clerk_id)
    )
    account_ids = [r[0] for r in accs_q.all()]
    if not account_ids:
        return 0

    await session.execute(
        delete(Position).where(Position.account_id.in_(account_ids))
    )
    if positions:
        rows = [{"id": uuid.uuid4(), **p} for p in positions]
        await session.execute(insert(Position), rows)
    await session.commit()
    return len(positions)


# ────────────────────────────────────────────────────────────────────────
# Reads para GET /portfolio/dashboard
# ────────────────────────────────────────────────────────────────────────
async def get_dashboard_data(
    session: AsyncSession, clerk_id: str
) -> dict:
    """Lee portfolio_snapshots + accounts + (compute positions on-the-fly via
    position_repo) y arma el shape del dashboard.

    No hace cómputo de la serie (eso lo hizo el cron). Solo lee.
    """
    from app.repositories import position_repo  # import local para evitar ciclo

    # latest snapshot
    snap_q = await session.execute(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.user_id == clerk_id)
        .order_by(PortfolioSnapshot.date.desc())
        .limit(2)
    )
    snaps = snap_q.scalars().all()
    latest = snaps[0] if snaps else None
    prev = snaps[1] if len(snaps) > 1 else None

    # trend (todos los snapshots ordenados asc)
    trend_q = await session.execute(
        select(PortfolioSnapshot.date, PortfolioSnapshot.total_value)
        .where(PortfolioSnapshot.user_id == clerk_id)
        .order_by(PortfolioSnapshot.date.asc())
    )
    trend = [
        {"date": r.date, "value": r.total_value or ZERO}
        for r in trend_q.all()
        if r.date is not None
    ]

    # accounts del user (para nombre/currency)
    accs_q = await session.execute(
        select(Account.id, Account.name, Account.currency).where(
            Account.user_id == clerk_id
        )
    )
    accounts_meta = {str(r.id): (r.name, r.currency) for r in accs_q.all()}

    # account distribution = breakdown_by_account del latest snapshot
    distribution = []
    if latest and latest.breakdown_by_account and latest.total_value:
        total = Decimal(str(latest.total_value))
        for acc_id_str, amount in latest.breakdown_by_account.items():
            amount_dec = Decimal(str(amount))
            name, curr = accounts_meta.get(acc_id_str, ("Cuenta", "USD"))
            distribution.append(
                {
                    "account_id": uuid.UUID(acc_id_str),
                    "name": name,
                    "amount": amount_dec,
                    "percentage": (amount_dec / total) if total > 0 else ZERO,
                    "currency": curr,
                }
            )

    # positions derivadas (mismo cálculo que GET /positions, reusa el SQL)
    positions = await position_repo.list_for_user(session, clerk_id)

    # summary
    if latest:
        total_value = latest.total_value or ZERO
        total_invested = latest.total_invested or ZERO
        unrealized = latest.unrealized_pnl or ZERO
        prev_value = (prev.total_value if prev else None) or ZERO
        return_pct = (
            ((total_value - prev_value) / prev_value) if prev_value > 0 else ZERO
        )
        summary = {
            "total_value": total_value,
            "total_invested": total_invested,
            "unrealized_pnl": unrealized,
            "total_return_pct": return_pct,
            "active_positions": len(positions),
            "linked_accounts": len(accounts_meta),
            "last_snapshot_date": latest.date,
        }
    else:
        # Sin snapshots (ej. user nuevo): devolvemos summary en cero, no 404.
        summary = {
            "total_value": ZERO,
            "total_invested": ZERO,
            "unrealized_pnl": ZERO,
            "total_return_pct": ZERO,
            "active_positions": len(positions),
            "linked_accounts": len(accounts_meta),
            "last_snapshot_date": None,
        }

    return {
        "summary": summary,
        "trend": trend,
        "account_distribution": distribution,
        "positions": positions,
    }


async def list_users_with_transactions(session: AsyncSession) -> list[str]:
    """Devuelve clerk_ids de usuarios que tienen al menos 1 transaction.
    Usado por el cron para iterar solo los users relevantes."""
    q = await session.execute(
        select(Profile.clerk_id)
        .join(Account, Account.user_id == Profile.clerk_id)
        .join(Transaction, Transaction.account_id == Account.id)
        .distinct()
    )
    return [r[0] for r in q.all()]
