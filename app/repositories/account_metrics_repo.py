import uuid
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.metrics import accounts as acc_math
from app.models.account_metrics import AccountDailyMetric, AccountMonthlyMetric
from app.models.portfolio_snapshot import PortfolioSnapshot


async def list_daily_for_account(
    session: AsyncSession, account_id: uuid.UUID
) -> list[AccountDailyMetric]:
    result = await session.execute(
        select(AccountDailyMetric)
        .where(AccountDailyMetric.account_id == account_id)
        .order_by(AccountDailyMetric.date.desc())
    )
    return list(result.scalars().all())


async def list_monthly_for_account(
    session: AsyncSession, account_id: uuid.UUID
) -> list[AccountMonthlyMetric]:
    result = await session.execute(
        select(AccountMonthlyMetric)
        .where(AccountMonthlyMetric.account_id == account_id)
        .order_by(AccountMonthlyMetric.date.desc())
    )
    return list(result.scalars().all())

async def get_latest_daily_metric_for_account(
    session: AsyncSession, account_id: uuid.UUID
) -> AccountDailyMetric | None:
    result = await session.execute(
        select(AccountDailyMetric)
        .where(AccountDailyMetric.account_id == account_id)
        .order_by(AccountDailyMetric.date.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()

async def get_latest_monthly_metric_for_account(
    session: AsyncSession, account_id: uuid.UUID
) -> AccountMonthlyMetric | None:
    result = await session.execute(
        select(AccountMonthlyMetric)
        .where(AccountMonthlyMetric.account_id == account_id)
        .order_by(AccountMonthlyMetric.date.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


# ── Cómputo app-side de métricas de cuenta (al subir PDF) ─────────────────────
# Espeja al cron `scripts_ghactions/accounts_*_metrics.py` pero scoped al user
# actual y vía SQLAlchemy async. La matemática es compartida (app.metrics.accounts)
# para que el fix de sortino/sharpe sea idéntico en ambos caminos.

def _dec(value) -> Decimal | None:
    """asyncpg exige Decimal (no float) para columnas Numeric."""
    return Decimal(str(value)) if value is not None else None


async def _value_series_for_user(
    session: AsyncSession, clerk_id: str
) -> dict[str, list]:
    """account_id(str) -> [(date, value), ...] asc, desde breakdown_by_account.

    Se lee con el ORM para que el JSONB se decodifique a dict de forma confiable.
    """
    result = await session.execute(
        select(PortfolioSnapshot.date, PortfolioSnapshot.breakdown_by_account)
        .where(
            PortfolioSnapshot.user_id == clerk_id,
            PortfolioSnapshot.breakdown_by_account.isnot(None),
        )
        .order_by(PortfolioSnapshot.date.asc())
    )
    series: dict[str, list] = {}
    for d, breakdown in result.all():
        for account_id, value in (breakdown or {}).items():
            series.setdefault(str(account_id), []).append((d, float(value)))
    return series


async def _cashflows_for_user(
    session: AsyncSession, clerk_id: str
) -> dict[tuple[str, object], float]:
    """(account_id(str), date) -> flujo neto del día (aportes - rescates)."""
    result = await session.execute(
        text("""
            SELECT t.account_id, t.date,
                   SUM(CASE WHEN t.kind='buy'  THEN t.quantity*t.price
                            WHEN t.kind='sell' THEN -t.quantity*t.price
                            ELSE 0 END) AS cf
            FROM transactions t
            JOIN accounts a ON a.id = t.account_id
            WHERE a.user_id = :clerk_id
              AND t.kind IN ('buy','sell')
              AND t.price IS NOT NULL AND t.date IS NOT NULL
            GROUP BY t.account_id, t.date
        """),
        {"clerk_id": clerk_id},
    )
    return {(str(acc), d): float(cf or 0) for acc, d, cf in result.all()}


async def _pnl_by_account_for_user(
    session: AsyncSession, clerk_id: str
) -> dict[str, float]:
    """pnl = realized_pnl + unrealized (qty*(last_close - avg_cost)) por cuenta."""
    result = await session.execute(
        text("""
            SELECT p.account_id,
                   COALESCE(SUM(
                       COALESCE(p.realized_pnl, 0)
                       + COALESCE(p.quantity * (lp.close - p.avg_cost), 0)
                   ), 0) AS pnl
            FROM positions p
            JOIN accounts a ON a.id = p.account_id
            LEFT JOIN LATERAL (
                SELECT close FROM asset_prices ap
                WHERE ap.asset_id = p.asset_id ORDER BY date DESC LIMIT 1
            ) lp ON TRUE
            WHERE a.user_id = :clerk_id
            GROUP BY p.account_id
        """),
        {"clerk_id": clerk_id},
    )
    return {str(acc): float(pnl) for acc, pnl in result.all()}


async def _assets_by_account_for_user(
    session: AsyncSession, clerk_id: str
) -> dict[str, list[str]]:
    """account_id(str) -> [asset_id(str), ...] (distintos, transados por el user)."""
    result = await session.execute(
        text("""
            SELECT DISTINCT t.account_id, t.asset_id
            FROM transactions t
            JOIN accounts a ON a.id = t.account_id
            WHERE a.user_id = :clerk_id AND t.asset_id IS NOT NULL
        """),
        {"clerk_id": clerk_id},
    )
    out: dict[str, list[str]] = {}
    for acc, asset in result.all():
        out.setdefault(str(acc), []).append(str(asset))
    return out


async def _asset_returns_for_user(
    session: AsyncSession, clerk_id: str
) -> dict[str, dict]:
    """asset_id(str) -> {date: retorno diario}, para los assets del user."""
    result = await session.execute(
        text("""
            SELECT ap.asset_id, ap.date, ap.close
            FROM asset_prices ap
            WHERE ap.asset_id IN (
                SELECT DISTINCT t.asset_id FROM transactions t
                JOIN accounts a ON a.id = t.account_id
                WHERE a.user_id = :clerk_id AND t.asset_id IS NOT NULL
            )
            ORDER BY ap.asset_id, ap.date ASC
        """),
        {"clerk_id": clerk_id},
    )
    returns: dict[str, dict] = {}
    prev: dict[str, tuple] = {}
    for asset, d, close in result.all():
        a = str(asset)
        c = float(close)
        if a in prev:
            _, pc = prev[a]
            if pc != 0:
                returns.setdefault(a, {})[d] = (c - pc) / pc
        prev[a] = (d, c)
    return returns


async def compute_and_store_daily_for_user(
    session: AsyncSession, clerk_id: str
) -> int:
    """Recalcula y reemplaza (idempotente) account_daily_metrics del user."""
    series = await _value_series_for_user(session, clerk_id)
    cashflows = await _cashflows_for_user(session, clerk_id)
    pnls = await _pnl_by_account_for_user(session, clerk_id)

    rows = []
    for account_id, pts in series.items():
        if not pts:
            continue
        rets = acc_math.adjusted_returns(pts, cashflows, account_id)
        rows.append({
            "id": str(uuid.uuid4()),
            "account_id": account_id,
            "date": pts[-1][0],
            # Acotar a los límites de cada columna Numeric (18,2)/(8,6).
            "pnl": _dec(acc_math.fit(pnls.get(account_id), 1e16)),
            "max_drawdown": _dec(acc_math.fit(acc_math.max_drawdown_twr(rets), 1e16)),
            "volatility": _dec(acc_math.fit(acc_math.volatility(rets), 100)),
        })

    await session.execute(
        text("""
            DELETE FROM account_daily_metrics
            WHERE account_id IN (SELECT id FROM accounts WHERE user_id = :clerk_id)
        """),
        {"clerk_id": clerk_id},
    )
    if rows:
        await session.execute(
            text("""
                INSERT INTO account_daily_metrics
                    (id, account_id, date, pnl, max_drawdown, volatility)
                VALUES (:id, :account_id, :date, :pnl, :max_drawdown, :volatility)
            """),
            rows,
        )
    await session.commit()
    return len(rows)


async def compute_and_store_monthly_for_user(
    session: AsyncSession, clerk_id: str
) -> int:
    """Recalcula y reemplaza (idempotente) account_monthly_metrics del user."""
    series = await _value_series_for_user(session, clerk_id)
    cashflows = await _cashflows_for_user(session, clerk_id)
    assets_by_account = await _assets_by_account_for_user(session, clerk_id)
    asset_returns = await _asset_returns_for_user(session, clerk_id)

    rows = []
    for account_id, pts in series.items():
        if len(pts) < 2:
            continue
        daily = acc_math.daily_adjusted_returns(pts, cashflows, account_id)
        monthly = acc_math.monthly_returns(daily)
        if not monthly:
            continue
        corr = acc_math.mean_pairwise_correlation(
            {a: asset_returns.get(a, {}) for a in assets_by_account.get(account_id, [])}
        )
        rows.append({
            "id": str(uuid.uuid4()),
            "account_id": account_id,
            "date": pts[-1][0],
            # twr/dietz(10,8) y var(18,2) se anulan si no caben; sharpe/sortino
            # ya vienen topados a ±99.9999 desde app.metrics.accounts.
            "twr": _dec(acc_math.fit(acc_math.twr(monthly), 100)),
            "dietz": _dec(acc_math.fit(
                acc_math.modified_dietz_last_month(pts, cashflows, account_id), 100)),
            "sharpe_ratio": _dec(acc_math.sharpe(monthly)),
            "var": _dec(acc_math.fit(acc_math.var_amount(monthly, pts[-1][1]), 1e16)),
            "sortino": _dec(acc_math.sortino(monthly)),
            "assets_correlation": _dec(acc_math.fit(corr, 10)),
        })

    await session.execute(
        text("""
            DELETE FROM account_monthly_metrics
            WHERE account_id IN (SELECT id FROM accounts WHERE user_id = :clerk_id)
        """),
        {"clerk_id": clerk_id},
    )
    if rows:
        await session.execute(
            text("""
                INSERT INTO account_monthly_metrics
                    (id, account_id, date, twr, dietz, sharpe_ratio, var, sortino, assets_correlation)
                VALUES (:id, :account_id, :date, :twr, :dietz, :sharpe_ratio, :var, :sortino, :assets_correlation)
            """),
            rows,
        )
    await session.commit()
    return len(rows)
