"""Reconstrucción de portafolio: time series de posiciones → portfolio_snapshots.

Algoritmo:
  1. Para cada usuario con transactions, traer todas sus transaction ordenadas por
     executed_at (join con accounts).
  2. Para cada día D entre min(executed_at).date() y today():
       - Actualizar running quantity / invested por (account, asset) hasta D.
       - Obtener precio del asset en D con forward-fill (último close con date <= D).
       - position_value(D) = quantity * precio.
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
  - total_invested = SUM(buy.quantity * buy.price + buy.fee) acumulado hasta D.
  - unrealized_pnl = total_value - total_invested_de_qty_actual. Simplificación
    para el MVP: no tracking de FIFO/LIFO; usamos avg_cost_acumulado.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date as date_type, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.asset_price import AssetPrice
from app.models.dividend import Dividend
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.position import Position
from app.models.transaction import Transaction, TransactionKind
from app.models.user import Profile

from app.routers.positions import post_daily_positions_metrics


ZERO = Decimal("0")


@dataclass
class _PairState:
    """Estado acumulado por par (account_id, asset_id)."""

    quantity: Decimal = ZERO
    invested: Decimal = ZERO  # acumulado de quantity*price+fee de buys
    realized_pnl: Decimal = ZERO  # acumulado al vender (sell.quantity * (sell.price - avg_cost))
    total_dividends: Decimal = ZERO
    total_fees: Decimal = ZERO
    last_tx_at: datetime | None = None

    @property
    def avg_cost(self) -> Decimal | None:
        return self.invested / self.quantity if self.quantity > 0 else None


async def compute_user_series(
    session: AsyncSession,
    clerk_id: str,
) -> tuple[list[dict], list[dict]]:
    """Devuelve (snapshots, positions_latest) sin tocar la DB.

    Calcula la serie temporal completa en memoria. Para un usuario típico (≤200
    transaction, ≤20 assets, ≤2 años) son <800 días × Python ops; OK para batch nocturno.
    """
    # ── 1. Traer todas las transactions del user + el currency de cada cuenta ──────
    transactions_query = await session.execute(
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
    transactions = transactions_query.all()
    if not transactions:
        return [], []

    # ── 2. Traer prices de los assets involucrados ────────────────────────
    asset_ids = {row.asset_id for row in transactions}
    asset_prices_query = await session.execute(
        select(AssetPrice.asset_id, AssetPrice.date, AssetPrice.close)
        .where(AssetPrice.asset_id.in_(asset_ids))
        .order_by(AssetPrice.asset_id, AssetPrice.date.asc())
    )
    # asset_id -> [(date, close), ...] ordenado asc
    prices_by_asset: dict[uuid.UUID, list[tuple[date_type, Decimal]]] = defaultdict(list)
    for r in asset_prices_query:
        prices_by_asset[r.asset_id].append((r.date, r.close))

    def price_on_or_before(asset_id: uuid.UUID, d: date_type) -> Decimal | None:
        """Forward-fill: último close con date <= d, o None si no hay ninguno aún."""
        series = prices_by_asset.get(asset_id, [])
        last: Decimal | None = None
        for pd, pc in series:
            if pd <= d:
                last = pc
            else:
                break
        return last

    # ── 3. Iteración día por día ──────────────────────────────────────────
    pair_state: dict[tuple[uuid.UUID, uuid.UUID], _PairState] = defaultdict(_PairState)
    account_meta: dict[uuid.UUID, tuple[str, str]] = {}
    for row in transactions:
        account_meta[row.account_id] = (row.account_currency, row.account_name)

    start_date = transactions[0].executed_at.date()
    end_date = datetime.now(tz=timezone.utc).date()

    transaction_index = 0
    snapshots: list[dict] = []

    current_date = start_date
    while current_date <= end_date:
        # ── consumir todas las transactions cuyo executed_at.date() <= current_date ────
        while transaction_index < len(transactions) and transactions[transaction_index].executed_at.date() <= current_date:
            transaction = transactions[transaction_index]
            state = pair_state[(transaction.account_id, transaction.asset_id)]
            quantity = transaction.quantity or ZERO
            price = transaction.price or ZERO
            fee = transaction.fee or ZERO

            if transaction.kind == TransactionKind.buy:
                state.quantity += quantity
                state.invested += quantity * price + fee
                state.total_fees += fee
            elif transaction.kind == TransactionKind.sell:
                avg = state.avg_cost or ZERO
                sell_qty = min(quantity, state.quantity) if state.quantity > ZERO else ZERO
                if sell_qty < quantity:
                    print(
                        f"[warn] venta excede tenencia (asset={transaction.asset_id}, "
                        f"account={transaction.account_id}): vende {quantity}, disponible "
                        f"{state.quantity}. Se ignora el exceso (data incompleta)."
                    )
                state.realized_pnl += sell_qty * (price - avg)
                state.invested -= avg * sell_qty
                state.quantity -= sell_qty
                state.total_fees += fee
            elif transaction.kind == TransactionKind.dividend:
                state.total_dividends += quantity
            elif transaction.kind == TransactionKind.fee:
                state.total_fees += fee if fee > 0 else quantity
            
            state.last_tx_at = transaction.executed_at
            transaction_index += 1

        # ── valuar todas las posiciones a current_date ────────────────────────
        # Usamos defaultdicts para acumular los valores separando por moneda
        total_value_by_curr: dict[str, Decimal] = defaultdict(lambda: ZERO)
        total_invested_by_curr: dict[str, Decimal] = defaultdict(lambda: ZERO)
        realized_pnl_by_curr: dict[str, Decimal] = defaultdict(lambda: ZERO)
        per_account: dict[str, Decimal] = defaultdict(lambda: ZERO)

        for (account_id, asset_id), state in pair_state.items():
            currency = account_meta[account_id][0]
            
            # El Realized PnL aplica siempre, incluso si la cantidad actual es 0 (posición cerrada)
            realized_pnl_by_curr[currency] += state.realized_pnl

            if state.quantity <= 0:
                continue

            price = price_on_or_before(asset_id, current_date)
            valuation_price = price if price is not None else (state.avg_cost or ZERO)
            mv = state.quantity * valuation_price
            
            # Acumulando por moneda
            total_value_by_curr[currency] += mv
            total_invested_by_curr[currency] += state.invested
            
            # Breakdown por cuenta
            per_account[str(account_id)] += mv

        # Calcular Unrealized PnL por moneda
        all_currencies = set(total_value_by_curr.keys()) | set(total_invested_by_curr.keys())
        unrealized_pnl_by_curr = {
            curr: total_value_by_curr[curr] - total_invested_by_curr[curr]
            for curr in all_currencies
        }

        snapshots.append(
            {
                "user_id": clerk_id,
                "date": current_date,
                # Convertimos todos los acumuladores a JSONB en el formato {"USD": "100.0"}
                "total_value": {k: str(v) for k, v in total_value_by_curr.items()},
                "total_invested": {k: str(v) for k, v in total_invested_by_curr.items()},
                "unrealized_pnl": {k: str(v) for k, v in unrealized_pnl_by_curr.items()},
                "realized_pnl": {k: str(v) for k, v in realized_pnl_by_curr.items()},
                "breakdown_by_currency": {k: str(v) for k, v in total_value_by_curr.items()},
                "breakdown_by_account": {k: str(v) for k, v in per_account.items()},
            }
        )
        current_date += timedelta(days=1)

    # ── 3.5 Dividendos desde la tabla `dividends` ─────────────────────────
    dividends_query = await session.execute(
        select(
            Dividend.account_id,
            Dividend.asset_id,
            func.coalesce(func.sum(Dividend.net_amount), 0),
        )
        .join(Account, Account.id == Dividend.account_id)
        .where(Account.user_id == clerk_id)
        .group_by(Dividend.account_id, Dividend.asset_id)
    )
    for account_id, asset_id, total in dividends_query:
        pair_state[(account_id, asset_id)].total_dividends += (total or ZERO)

    # ── 4. Estado latest de positions ─────────────────────────────────────
    now = datetime.now(tz=timezone.utc)
    positions_latest = []
    for (account_id, asset_id), state in pair_state.items():
        if state.quantity == 0 and state.realized_pnl == 0 and state.total_dividends == 0:
            continue  
        positions_latest.append(
            {
                "account_id": account_id,
                "asset_id": asset_id,
                "quantity": state.quantity,
                "avg_cost": state.avg_cost,
                "realized_pnl": state.realized_pnl,
                "total_dividends": state.total_dividends,
                "total_fees": state.total_fees,
                "last_transaction_at": state.last_tx_at,
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
    session: AsyncSession, user, positions: list[dict]
) -> int:
    """Reemplaza positions del user (DELETE las de sus accounts + INSERT)."""
    # accounts del user
    accs_q = await session.execute(
        select(Account.id).where(Account.user_id == user.clerk_id)
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

    for row in rows:
        await post_daily_positions_metrics(row["id"], user, session)

    return len(positions)


# ────────────────────────────────────────────────────────────────────────
# Reads para GET /portfolio/dashboard
# ────────────────────────────────────────────────────────────────────────
# TODO: Plantear eliminarlo para solo usar la versión summary, trend + postions
# (por un tema de ser menos demandante)
async def get_dashboard_data(
    session: AsyncSession,
    clerk_id: str,
    trend_from: date_type | None = None,
    trend_to: date_type | None = None,
) -> dict:
    """Retorna dashboard completo orquestando las tres funciones especializadas.
    
    Combina:
    - Summary: métricas totales + distribución por cuenta
    - Trend: serie temporal filtrada por rango de fechas
    - Positions: listado de posiciones activas con valuaciones derivadas
    """
    from app.repositories import position_repo
    
    # Ejecutar las tres queries en paralelo (podrían ser concurrentes)
    summary_data = await get_portfolio_summary_data(session, clerk_id)
    trend = await get_portfolio_trend_data(session, clerk_id, trend_from, trend_to)
    positions = await position_repo.list_for_user_portfolio(session, clerk_id, limit=10_000)
    
    return {
        "summary": summary_data["summary"],
        "trend": trend,
        "account_distribution": summary_data["account_distribution"],
        "positions": positions,
    }


# ----------------------------------------------
# Para GET /portfolio/summary
# ----------------------------------------------
# Retorna solo summary + account distibution
async def get_portfolio_summary_data(session: AsyncSession, clerk_id: str) -> dict:
    from app.repositories import position_repo
    import uuid
    from decimal import Decimal

    ZERO = Decimal("0")

    # Obtener los últimos 2 snapshot guardados en la base de datos
    snapshots_query = await session.execute(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.user_id == clerk_id)
        .order_by(PortfolioSnapshot.date.desc())
        .limit(2)
    )
    snapshots = snapshots_query.scalars().all()
    latest = snapshots[0] if snapshots else None
    prev = snapshots[1] if len(snapshots) > 1 else None

    # Obtener todas las accounts del user (Obtengo nombre y currency)
    accs_q = await session.execute(
        select(Account.id, Account.name, Account.currency).where(
            Account.user_id == clerk_id
        )
    )
    accounts_meta = {str(r.id): (r.name, r.currency) for r in accs_q.all()}

    # Extraer métricas globales agrupadas por moneda directamente del JSONB
    total_value_by_currency: dict[str, Decimal] = {}
    total_invested_by_currency: dict[str, Decimal] = {}
    unrealized_pnl_by_currency: dict[str, Decimal] = {}

    if latest:
        if latest.total_value:
            total_value_by_currency = {k: Decimal(str(v)) for k, v in latest.total_value.items()}
        if latest.total_invested:
            total_invested_by_currency = {k: Decimal(str(v)) for k, v in latest.total_invested.items()}
        if latest.unrealized_pnl:
            unrealized_pnl_by_currency = {k: Decimal(str(v)) for k, v in latest.unrealized_pnl.items()}

    # Calculo account distribution basado en el breakdown_by_account del latest snapshot
    distribution = []
    if latest and latest.breakdown_by_account:
        for acc_id_str, amount in latest.breakdown_by_account.items():
            amount_dec = Decimal(str(amount))
            name, curr = accounts_meta.get(acc_id_str, ("Cuenta", "USD"))
            total_curr = total_value_by_currency.get(curr, ZERO)
            distribution.append(
                {
                    "account_id": uuid.UUID(acc_id_str),
                    "name": name,
                    "amount": amount_dec,
                    "percentage": (
                        (amount_dec / total_curr) if total_curr > 0 else ZERO
                    ),
                    "currency": curr,
                }
            )

    # Obtengo la cantidas de positons del usuario
    n_positions = await position_repo.count_for_user(session, clerk_id)
    
    # Calculo valores globales según si hay 1 o varias currencies
    user_currencies = set(c for _, c in accounts_meta.values())
    is_single_currency = len(user_currencies) == 1

    if is_single_currency:
        only = next(iter(user_currencies))
        scalar_value = total_value_by_currency.get(only, ZERO)
        scalar_invested = total_invested_by_currency.get(only, ZERO)
        scalar_unrealized = unrealized_pnl_by_currency.get(only, ZERO)
    else:
        scalar_value = None
        scalar_invested = None
        scalar_unrealized = None

    # total_return_pct adaptado para extraer el valor escalar de los diccionarios previos
    return_pct: Decimal | None = None
    if is_single_currency and latest and prev and latest.total_value and prev.total_value:
        prev_v_str = prev.total_value.get(only, "0")
        latest_v_str = latest.total_value.get(only, "0")
        
        prev_v = Decimal(str(prev_v_str))
        if prev_v > 0:
            return_pct = (Decimal(str(latest_v_str)) - prev_v) / prev_v

    summary = {
        "total_value": scalar_value,
        "total_invested": scalar_invested,
        "unrealized_pnl": scalar_unrealized,
        "total_value_by_currency": total_value_by_currency,
        "total_invested_by_currency": total_invested_by_currency,
        "unrealized_pnl_by_currency": unrealized_pnl_by_currency,
        "total_return_pct": return_pct,
        "active_positions": n_positions,
        "linked_accounts": len(accounts_meta),
        "last_snapshot_date": latest.date if latest else None,
    }

    return {
        "summary": summary,
        "account_distribution": distribution
    }

# -------------------------------------
# Para GET /portfolio/trend
# -------------------------------------
# Retorna serie temporal (trend) del valor total del portafolio
# Cuenta con filtro de fechas
async def get_portfolio_trend_data(
    session: AsyncSession, 
    clerk_id: str, 
    trend_from: date_type | None = None, 
    trend_to: date_type | None = None
) -> list[dict]:
    from decimal import Decimal

    stmt = select(PortfolioSnapshot.date, PortfolioSnapshot.total_value).where(
        PortfolioSnapshot.user_id == clerk_id
    )
    if trend_from:
        stmt = stmt.where(PortfolioSnapshot.date >= trend_from)
    if trend_to:
        stmt = stmt.where(PortfolioSnapshot.date <= trend_to)
        
    stmt = stmt.order_by(PortfolioSnapshot.date.asc())
    q = await session.execute(stmt)
    
    # Se retorna un diccionario con el desglose por moneda en vez de un solo "value"
    return [
        {
            "date": row.date,
            "values_by_currency": {
                k: Decimal(str(v)) for k, v in (row.total_value or {}).items()
            }
        } 
        for row in q.all()
    ]

async def list_users_with_transactions(session: AsyncSession) -> list[str]:
    """Devuelve el objeto user de usuarios que tienen al menos 1 transaction.
    Usado por el cron para iterar solo los users relevantes."""
    q = await session.execute(
        select(Profile)
        .join(Account, Account.user_id == Profile.clerk_id)
        .join(Transaction, Transaction.account_id == Account.id)
        .distinct()
    )
    return [r[0] for r in q.all()]




# Función para reconstruir portafolio (snapshot + positions) de 1 usuario
# Reutiliza funciones implementadas anteriormente
# TODO: Evaluar si es muy pesado de ejecutar, en caso de que sí considerar plantear: 
# a) Límites de cuántos datos considera
# b) Sistema alterno de reconstrucción menos pesado (update datos en vez de eliminar)??
async def reconstruct_user_portfolio(session: AsyncSession, user) -> tuple[int, int]:
    """
    Reconstruye el portafolio (snapshots y posiciones) para usuario dado usando las funciones existentes
    Devuelve una tupla (n_snapshots, n_positions) con la cantidad de registros insertados
    """
    # Calcular la serie temporal completa en memoria para este usuario específico
    snapshots, positions = await compute_user_series(session, user.clerk_id)
    # Si el usuario no tiene transacciones, evitamos operaciones innecesarias
    if not snapshots and not positions:
        return 0, 0
    # Reemplazar de forma idempotente los snapshots
    n_snaps = await replace_snapshots(session, user.clerk_id, snapshots)
    # Reemplazar las posiciones actuales
    n_pos = await replace_positions(session, user, positions)
    
    return n_snaps, n_pos