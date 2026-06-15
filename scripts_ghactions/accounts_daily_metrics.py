"""Métricas DIARIAS a nivel de CUENTA → account_daily_metrics.

Calcula, por cuenta:
  - volatility    = stdev(retornos diarios AJUSTADOS por flujo, últimos 252) * sqrt(252)
  - max_drawdown  = mínimo (I[d] - peak) / peak * 100  sobre el índice TWR
  - pnl           = realized_pnl + unrealized  (desde positions + último asset_price)

Clave: la serie de valor de la cuenta (portfolio_snapshots.breakdown_by_account)
incluye los APORTES/RESCATES. Para medir rendimiento/volatilidad reales hay que
descontar el flujo de caja del día:

    r[d] = (V[d] - V[d-1] - CF[d]) / V[d-1]          (retorno ajustado por flujo)
    I[d] = I[d-1] * (1 + r[d])                        (índice time-weighted)
    CF[d] = Σ(buy.qty*price) - Σ(sell.qty*price)      (dinero que entra/sale ese día)

Así una cuenta que sube solo por aportes NO marca "retorno"; volatility y
max_drawdown reflejan el desempeño de la inversión, no los movimientos de plata.

Upsert idempotente: DELETE de las cuentas tocadas + INSERT (las tablas
account_*_metrics no tienen UNIQUE constraint).

Uso:
    DATABASE_URL='postgresql://...neon...' python scripts_ghactions/accounts_daily_metrics.py          # dry-run
    DATABASE_URL='postgresql://...neon...' python scripts_ghactions/accounts_daily_metrics.py --apply   # escribe
"""
import argparse
import os
import statistics
import uuid
from collections import defaultdict
from datetime import date
from math import sqrt

import psycopg2
from psycopg2.extras import execute_values

TRADING_DAYS = 252


def _fit(value, max_abs, label="", account_id=""):
    """Devuelve None si el valor no cabe en su columna Numeric (evita que una
    cuenta con data sucia reviente toda la corrida por 'numeric field overflow').
    max_abs = límite por precisión/escala (ej. Numeric(8,6) -> 100)."""
    if value is None:
        return None
    if abs(value) >= max_abs:
        print(f"[warn] {label}={value} fuera de rango para {account_id[:8]} -> NULL")
        return None
    return value


def connection_bdd():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    return conn, conn.cursor()


def close_bdd(conn, cur):
    cur.close()
    conn.close()


def build_value_series(cur) -> dict[str, list[tuple[date, float]]]:
    """account_id -> [(date, value), ...] asc, desde breakdown_by_account."""
    cur.execute(
        "SELECT date, breakdown_by_account FROM portfolio_snapshots "
        "WHERE breakdown_by_account IS NOT NULL ORDER BY date ASC"
    )
    series: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for d, breakdown in cur.fetchall():
        for account_id, value in (breakdown or {}).items():
            series[account_id].append((d, float(value)))
    return series


def build_cashflows(cur) -> dict[tuple[str, date], float]:
    """(account_id, date) -> flujo neto de caja del día (aportes - rescates)."""
    cur.execute(
        """
        SELECT account_id, date,
               SUM(CASE WHEN kind='buy'  THEN quantity*price
                        WHEN kind='sell' THEN -quantity*price ELSE 0 END) AS cf
        FROM transactions
        WHERE kind IN ('buy','sell') AND price IS NOT NULL AND date IS NOT NULL
        GROUP BY account_id, date
        """
    )
    return {(str(acc), d): float(cf or 0) for acc, d, cf in cur.fetchall()}


def adjusted_returns(pts, cashflows, account_id) -> list[float]:
    """Retornos diarios descontando el flujo de caja del día."""
    out = []
    for i in range(1, len(pts)):
        prev_v = pts[i - 1][1]
        if prev_v == 0:
            continue
        d = pts[i][0]
        cf = cashflows.get((account_id, d), 0.0)
        out.append((pts[i][1] - prev_v - cf) / prev_v)
    return out


def volatility(returns: list[float]) -> float | None:
    r = returns[-TRADING_DAYS:]
    if len(r) < 2:
        return None
    return statistics.stdev(r) * sqrt(TRADING_DAYS)


def max_drawdown_twr(returns: list[float]) -> float:
    """Drawdown sobre el índice time-weighted (no contaminado por flujos)."""
    idx = 1.0
    peak = 1.0
    mdd = 0.0
    for r in returns:
        idx *= (1 + r)
        peak = max(peak, idx)
        mdd = min(mdd, (idx - peak) / peak * 100 if peak != 0 else 0.0)
    return mdd


def pnl_by_account(cur) -> dict[str, float]:
    """pnl = realized_pnl + unrealized (qty*(last_close - avg_cost)) por cuenta."""
    cur.execute(
        """
        SELECT p.account_id,
               COALESCE(SUM(
                   COALESCE(p.realized_pnl, 0)
                   + COALESCE(p.quantity * (lp.close - p.avg_cost), 0)
               ), 0) AS pnl
        FROM positions p
        LEFT JOIN LATERAL (
            SELECT close FROM asset_prices ap
            WHERE ap.asset_id = p.asset_id ORDER BY date DESC LIMIT 1
        ) lp ON TRUE
        GROUP BY p.account_id
        """
    )
    return {str(acc): float(pnl) for acc, pnl in cur.fetchall()}


def accounts_for_clerk(cur, clerk_id: str) -> set[str]:
    cur.execute("SELECT id FROM accounts WHERE user_id = %s", (clerk_id,))
    return {str(r[0]) for r in cur.fetchall()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="escribe en account_daily_metrics (default: dry-run)")
    ap.add_argument("--clerk-id", default=None, help="acotar a las cuentas de un usuario")
    args = ap.parse_args()

    conn, cur = connection_bdd()
    series = build_value_series(cur)
    cashflows = build_cashflows(cur)
    pnls = pnl_by_account(cur)

    scope = accounts_for_clerk(cur, args.clerk_id) if args.clerk_id else None

    rows = []  # (account_id, date, pnl, max_drawdown, volatility)
    print(f"{'account_id':38}{'fecha':>12}{'pnl':>16}{'max_dd%':>10}{'vol(anual)':>12}")
    for account_id, pts in series.items():
        if scope is not None and account_id not in scope:
            continue
        if not pts:
            continue
        rets = adjusted_returns(pts, cashflows, account_id)
        vol = volatility(rets)
        mdd = max_drawdown_twr(rets)
        pnl = pnls.get(account_id)
        last_date = pts[-1][0]
        # Acotar a los límites de cada columna Numeric (8,6)/(18,2).
        rows.append((
            account_id, last_date,
            _fit(pnl, 1e16, "pnl", account_id),
            _fit(mdd, 1e16, "max_drawdown", account_id),
            _fit(vol, 100, "volatility", account_id),
        ))
        print(f"{account_id:38}{str(last_date):>12}"
              f"{(pnl if pnl is not None else float('nan')):>16,.2f}"
              f"{mdd:>10.2f}{(vol if vol is not None else float('nan')):>12.4f}")

    if not args.apply:
        print(f"\n  DRY-RUN: {len(rows)} cuentas calculadas, no se escribió nada. Usa --apply.")
        close_bdd(conn, cur)
        return 0

    account_ids = [r[0] for r in rows]
    if account_ids:
        cur.execute(
            "DELETE FROM account_daily_metrics WHERE account_id = ANY(%s::uuid[])",
            (account_ids,),
        )
        # `id` no tiene default a nivel de BD → se genera acá (como en el resto
        # de los INSERT crudos del repo).
        rows_with_id = [(str(uuid.uuid4()), *r) for r in rows]
        execute_values(
            cur,
            "INSERT INTO account_daily_metrics "
            "(id, account_id, date, pnl, max_drawdown, volatility) VALUES %s",
            rows_with_id,
        )
        conn.commit()
    print(f"\n  ✅ {len(rows)} filas escritas en account_daily_metrics.")
    close_bdd(conn, cur)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
