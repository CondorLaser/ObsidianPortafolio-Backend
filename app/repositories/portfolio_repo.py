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

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
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
        return self.invested / self.qty if self.qty > 0 else None


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

    tx_idx = 0
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
                # En este schema, tx.quantity con kind=dividend representa el
                # monto cash del dividendo (no unidades); no toca quantity.
                st.total_dividends += qty
            elif tx.kind == TransactionKind.fee:
                # Modelado dual: kind=fee usa fee si está, si no toma qty (legacy).
                st.total_fees += fee if fee > 0 else qty
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
                # JSONB acepta strings y los Decimals los preservamos como tal
                # (evita pérdida de precisión por float).
                "breakdown_by_currency": {k: str(v) for k, v in per_currency.items()},
                "breakdown_by_account": {k: str(v) for k, v in per_account.items()},
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
# TODO: Plantear eliminarlo para solo usar la versión summary, trend + postions
# (por un tema de ser menos demandante)
async def get_dashboard_data(
    session: AsyncSession,
    clerk_id: str,
    trend_from: date_type | None = None,
    trend_to: date_type | None = None,
) -> dict:
    """Lee portfolio_snapshots + accounts + (compute positions on-the-fly via
    position_repo). trend_from/trend_to filtran la serie del trend."""
    from app.repositories import position_repo  # import local para evitar ciclo

    # latest snapshot (independiente del rango de trend)
    snap_q = await session.execute(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.user_id == clerk_id)
        .order_by(PortfolioSnapshot.date.desc())
        .limit(2)
    )
    snaps = snap_q.scalars().all()
    latest = snaps[0] if snaps else None
    prev = snaps[1] if len(snaps) > 1 else None

    # trend (filtrado por rango opcional)
    trend_stmt = (
        select(PortfolioSnapshot.date, PortfolioSnapshot.total_value)
        .where(PortfolioSnapshot.user_id == clerk_id)
        .order_by(PortfolioSnapshot.date.asc())
    )
    if trend_from is not None:
        trend_stmt = trend_stmt.where(PortfolioSnapshot.date >= trend_from)
    if trend_to is not None:
        trend_stmt = trend_stmt.where(PortfolioSnapshot.date <= trend_to)
    trend_q = await session.execute(trend_stmt)
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

    # ── breakdowns por currency ──
    # total_value_by_currency viene del snapshot.breakdown_by_currency.
    # total_invested/unrealized se recomputan desde positions (que están
    # materializadas por el cron) agrupadas por la currency de su account.
    total_value_by_currency: dict[str, Decimal] = {}
    if latest and latest.breakdown_by_currency:
        total_value_by_currency = {
            curr: Decimal(str(amount))
            for curr, amount in latest.breakdown_by_currency.items()
        }

    # positions materializadas (1 row por par account+asset)
    pos_q = await session.execute(
        select(Position, Account.currency)
        .join(Account, Account.id == Position.account_id)
        .where(Account.user_id == clerk_id)
    )
    total_invested_by_currency: dict[str, Decimal] = {}
    for pos, curr in pos_q.all():
        invested = (pos.quantity or ZERO) * (pos.avg_cost or ZERO)
        total_invested_by_currency[curr] = (
            total_invested_by_currency.get(curr, ZERO) + invested
        )

    # unrealized_by_currency = total_value - total_invested por currency
    all_currencies = set(total_value_by_currency) | set(total_invested_by_currency)
    unrealized_pnl_by_currency = {
        curr: total_value_by_currency.get(curr, ZERO)
        - total_invested_by_currency.get(curr, ZERO)
        for curr in all_currencies
    }

    # account distribution = breakdown_by_account del latest snapshot.
    # percentage normaliza solo contra el TOTAL DE LA MISMA CURRENCY (no
    # mezclamos CLP+USD en el denominador).
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

    # TODO: el cron ahora materializa la tabla `positions`, pero acá seguimos
    # recomputando on-the-fly via position_repo (que hace su propio SQL).
    # Conviene leer de `positions` directamente y joinear con `assets` para
    # symbol/name + último asset_price para market_value. Se mantiene como
    # estaba para no romper el shape de PositionDerived.
    #
    # Usa list_for_user_portfolio (derivada en runtime → PositionDerived con
    # last_price/market_value/unrealized_pnl). NO usar list_for_user, que tras
    # la PR #29 devuelve la posición materializada (shape distinto). El dashboard
    # quiere TODAS las posiciones activas, así que se sube el limit.
    positions = await position_repo.list_for_user_portfolio(
        session, clerk_id, limit=10_000
    )

    # summary: si hay UNA sola currency llenamos los Decimal escalares;
    # si hay múltiples, NULL en escalares y el frontend usa los *_by_currency.
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

    # total_return_pct se calcula solo cuando hay 1 currency y un snapshot
    # previo válido (sin FX, comparar valores multi-currency no tiene sentido).
    return_pct: Decimal | None = None
    if is_single_currency and latest and prev and latest.total_value and prev.total_value:
        prev_v = Decimal(str(prev.total_value))
        if prev_v > 0:
            return_pct = (Decimal(str(latest.total_value)) - prev_v) / prev_v

    summary = {
        "total_value": scalar_value,
        "total_invested": scalar_invested,
        "unrealized_pnl": scalar_unrealized,
        "total_value_by_currency": total_value_by_currency,
        "total_invested_by_currency": total_invested_by_currency,
        "unrealized_pnl_by_currency": unrealized_pnl_by_currency,
        "total_return_pct": return_pct,
        "active_positions": len(positions),
        "linked_accounts": len(accounts_meta),
        "last_snapshot_date": latest.date if latest else None,
    }

    return {
        "summary": summary,
        "trend": trend,
        "account_distribution": distribution,
        "positions": positions,
    }


# ----------------------------------------------
# Para GET /portfolio/summary
# ----------------------------------------------
# Retorna solo summary + account distibution
async def get_portfolio_summary_data(session: AsyncSession, clerk_id: str) -> dict:
    # Obtener el último snapshot guardado en la base de datos
    latest_snap_q = await session.execute(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.user_id == clerk_id)
        .order_by(PortfolioSnapshot.date.desc())
        .limit(1)
    )
    latest: PortfolioSnapshot | None = latest_snap_q.scalar_one_or_none()

    # Obtener el snapshot inmediatamente previo para calcular el retorno diario
    prev: PortfolioSnapshot | None = None
    if latest:
        prev_snap_q = await session.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.user_id == clerk_id, PortfolioSnapshot.date < latest.date)
            .order_by(PortfolioSnapshot.date.desc())
            .limit(1)
        )
        prev = prev_snap_q.scalar_one_or_none()

    # Obtener metadatos de las cuentas para armar account distribution
    accounts_q = await session.execute(
        select(Account).where(Account.user_id == clerk_id)
    )
    accounts_meta = accounts_q.scalars().all()
    account_names = {a.id: a.name for a in accounts_meta}
    account_currencies = {a.id: a.currency for a in accounts_meta}

    # Obtener las posiciones vigentes del usuario
    pos_q = await session.execute(
        select(Position)
        .join(Account, Account.id == Position.account_id)
        .where(Account.user_id == clerk_id)
    )
    positions = pos_q.scalars().all()

    # Calcular la distribución
    dist_by_acc: dict[uuid.UUID, Decimal] = {}
    if latest and latest.breakdown_by_account:
        for acc_id_str, val in latest.breakdown_by_account.items():
            try:
                dist_by_acc[uuid.UUID(acc_id_str)] = Decimal(str(val))
            except ValueError:
                continue
    total_val_snapshots = sum(dist_by_acc.values()) if dist_by_acc else Decimal("0")

    distribution = []
    for acc_id, amt in dist_by_acc.items():
        pct = (amt / total_val_snapshots) if total_val_snapshots > 0 else Decimal("0")
        distribution.append({
            "account_id": acc_id,
            "name": account_names.get(acc_id, f"Cuenta {str(acc_id)[:6]}"),
            "amount": amt,
            "percentage": pct,
            "currency": account_currencies.get(acc_id, "USD")
        })

    # Procesar inversiones, totales y no realizados por moneda
    total_value_by_currency = {}
    total_invested_by_currency = {}
    unrealized_pnl_by_currency = {}

    if latest:
        if latest.breakdown_by_currency:
            for cur, val in latest.breakdown_by_currency.items():
                total_value_by_currency[cur] = Decimal(str(val))
        
        # Calcular los invertidos a partir de las posiciones materializadas
        for p in positions:
            cur = account_currencies.get(p.account_id, "USD")
            
            # SOLUCIÓN: Calcular invested = quantity * avg_cost (manejando Nones)
            qty = p.quantity if p.quantity is not None else Decimal("0")
            cost = p.avg_cost if p.avg_cost is not None else Decimal("0")
            p_invested = qty * cost
            
            total_invested_by_currency[cur] = total_invested_by_currency.get(cur, Decimal("0")) + p_invested

        # Calcular Unrealized PnL por moneda
        for cur, v_val in total_value_by_currency.items():
            i_val = total_invested_by_currency.get(cur, Decimal("0"))
            unrealized_pnl_by_currency[cur] = v_val - i_val

    # Lógica multi-moneda (si tiene 1 sola moneda, se exponen escalares limpios = valor unificado)
    unique_currencies = set(account_currencies.values())
    is_single_currency = len(unique_currencies) == 1
    main_currency = list(unique_currencies)[0] if is_single_currency else None

    scalar_value = total_value_by_currency.get(main_currency) if is_single_currency else None
    scalar_invested = total_invested_by_currency.get(main_currency) if is_single_currency else None
    scalar_unrealized = unrealized_pnl_by_currency.get(main_currency) if is_single_currency else None

    return_pct = None
    if is_single_currency and latest and prev and latest.total_value and prev.total_value:
        prev_v = Decimal(str(prev.total_value))
        if prev_v > 0:
            return_pct = (Decimal(str(latest.total_value)) - prev_v) / prev_v

    summary = {
        "total_value": scalar_value,
        "total_invested": scalar_invested,
        "unrealized_pnl": scalar_unrealized,
        "total_value_by_currency": total_value_by_currency,
        "total_invested_by_currency": total_invested_by_currency,
        "unrealized_pnl_by_currency": unrealized_pnl_by_currency,
        "total_return_pct": return_pct,
        "active_positions": len(positions),
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
    stmt = select(PortfolioSnapshot.date, PortfolioSnapshot.total_value).where(
        PortfolioSnapshot.user_id == clerk_id
    )
    if trend_from:
        stmt = stmt.where(PortfolioSnapshot.date >= trend_from)
    if trend_to:
        stmt = stmt.where(PortfolioSnapshot.date <= trend_to)
        
    stmt = stmt.order_by(PortfolioSnapshot.date.asc())
    
    q = await session.execute(stmt)
    return [{"date": row.date, "value": Decimal(str(row.total_value or 0))} for row in q.all()]


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




# Función para reconstruir portafolio (snapshot + positions) de 1 usuario
# Reutiliza funciones implementadas anteriormente
# TODO: Evaluar si es muy pesado de ejecutar, en caso de que sí considerar plantear: 
# a) Límites de cuántos datos considera
# b) Sistema alterno de reconstrucción menos pesado (update datos en vez de eliminar)??
async def reconstruct_user_portfolio(session: AsyncSession, clerk_id: str) -> tuple[int, int]:
    """
    Reconstruye el portafolio (snapshots y posiciones) para usuario dado usando las funciones existentes
    Devuelve una tupla (n_snapshots, n_positions) con la cantidad de registros insertados
    """
    # Calcular la serie temporal completa en memoria para este usuario específico
    snapshots, positions = await compute_user_series(session, clerk_id)
    # Si el usuario no tiene transacciones, evitamos operaciones innecesarias
    if not snapshots and not positions:
        return 0, 0
    # Reemplazar de forma idempotente los snapshots
    n_snaps = await replace_snapshots(session, clerk_id, snapshots)
    # Reemplazar las posiciones actuales
    n_pos = await replace_positions(session, clerk_id, positions)
    
    return n_snaps, n_pos