"""Métricas MENSUALES a nivel de CUENTA → account_monthly_metrics.

Por cuenta (una fila, "as of" la última fecha):
  - twr                = retorno time-weighted acumulado (trailing 12 meses)
  - dietz              = Modified Dietz del último mes
  - sharpe_ratio       = (media ret. mensual / stdev) * sqrt(12)        (rf=0)
  - sortino            = (media ret. mensual / downside dev) * sqrt(12) (rf=0)
  - var                = |percentil 5% de retornos mensuales| * valor actual (CLP/USD)
  - assets_correlation = correlación media pairwise entre los assets de la cuenta

Reusa la lógica del daily: serie de valor (breakdown_by_account) + flujo de caja
para retornos AJUSTADOS  r[d] = (V[d]-V[d-1]-CF[d]) / V[d-1]. Los retornos
mensuales se arman encadenando los diarios (TWR): (Π(1+r) por mes) - 1.

Upsert idempotente: DELETE de las cuentas tocadas + INSERT.

Uso:
    DATABASE_URL='postgresql://...neon...' python scripts_ghactions/accounts_monthly_metrics.py            # dry-run
    DATABASE_URL='postgresql://...neon...' python scripts_ghactions/accounts_monthly_metrics.py --apply --clerk-id X
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

MONTHS = 12


def connection_bdd():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    return conn, conn.cursor()


def close_bdd(conn, cur):
    cur.close()
    conn.close()


# ── Fuentes de datos (idénticas al daily) ─────────────────────────────────
def build_value_series(cur):
    cur.execute(
        "SELECT date, breakdown_by_account FROM portfolio_snapshots "
        "WHERE breakdown_by_account IS NOT NULL ORDER BY date ASC"
    )
    series = defaultdict(list)
    for d, breakdown in cur.fetchall():
        for account_id, value in (breakdown or {}).items():
            series[account_id].append((d, float(value)))
    return series


def build_cashflows(cur):
    cur.execute(
        """
        SELECT account_id, date,
               SUM(CASE WHEN kind='buy' THEN quantity*price
                        WHEN kind='sell' THEN -quantity*price ELSE 0 END) AS cf
        FROM transactions
        WHERE kind IN ('buy','sell') AND price IS NOT NULL AND date IS NOT NULL
        GROUP BY account_id, date
        """
    )
    return {(str(acc), d): float(cf or 0) for acc, d, cf in cur.fetchall()}


def accounts_for_clerk(cur, clerk_id):
    cur.execute("SELECT id FROM accounts WHERE user_id = %s", (clerk_id,))
    return {str(r[0]) for r in cur.fetchall()}


def account_assets(cur, account_id):
    cur.execute(
        "SELECT DISTINCT asset_id FROM transactions WHERE account_id = %s", (account_id,)
    )
    return [str(r[0]) for r in cur.fetchall()]


def asset_daily_returns(cur, asset_id):
    cur.execute(
        "SELECT date, close FROM asset_prices WHERE asset_id = %s ORDER BY date ASC",
        (asset_id,),
    )
    px = [(d, float(c)) for d, c in cur.fetchall()]
    return {
        px[i][0]: (px[i][1] - px[i - 1][1]) / px[i - 1][1]
        for i in range(1, len(px))
        if px[i - 1][1] != 0
    }


# ── Cálculos ──────────────────────────────────────────────────────────────
def daily_adjusted_returns(pts, cashflows, account_id):
    """[(date, r), ...] con r ajustado por flujo."""
    out = []
    for i in range(1, len(pts)):
        prev_v = pts[i - 1][1]
        if prev_v == 0:
            continue
        d = pts[i][0]
        cf = cashflows.get((account_id, d), 0.0)
        out.append((d, (pts[i][1] - prev_v - cf) / prev_v))
    return out


def monthly_returns(daily):
    """Encadena retornos diarios a mensuales (TWR): por mes Π(1+r)-1.
    Devuelve [((year, month), ret), ...] ordenado asc."""
    prod = defaultdict(lambda: 1.0)
    for d, r in daily:
        prod[(d.year, d.month)] *= (1 + r)
    return [(k, v - 1.0) for k, v in sorted(prod.items())]


def twr(monthly):
    rets = [r for _, r in monthly][-MONTHS:]
    acc = 1.0
    for r in rets:
        acc *= (1 + r)
    return acc - 1.0


def sharpe(monthly):
    rets = [r for _, r in monthly]
    if len(rets) < 2:
        return None
    sd = statistics.stdev(rets)
    if sd == 0:
        return None
    return (statistics.mean(rets) / sd) * sqrt(MONTHS)


def sortino(monthly):
    rets = [r for _, r in monthly]
    if len(rets) < 2:
        return None
    downside = sqrt(sum(min(r, 0.0) ** 2 for r in rets) / len(rets))
    if downside == 0:
        return None
    return (statistics.mean(rets) / downside) * sqrt(MONTHS)


def var_amount(monthly, current_value):
    """VaR histórico: |percentil 5% de retornos mensuales| * valor actual."""
    rets = sorted(r for _, r in monthly)
    if len(rets) < 2 or current_value is None:
        return None
    idx = max(0, int(0.05 * len(rets)) - 1) if len(rets) >= 20 else 0
    p5 = rets[idx]
    return abs(min(p5, 0.0)) * float(current_value)


def modified_dietz_last_month(pts, cashflows, account_id):
    """Modified Dietz del último mes presente en la serie."""
    if len(pts) < 2:
        return None
    last_d = pts[-1][0]
    y, m = last_d.year, last_d.month
    month_pts = [(d, v) for d, v in pts if d.year == y and d.month == m]
    if len(month_pts) < 2:
        return None
    bmd = month_pts[0][0]
    emd = month_pts[-1][0]
    bv = month_pts[0][1]
    ev = month_pts[-1][1]
    days = max((emd - bmd).days, 1)
    cf_total = 0.0
    weighted = 0.0
    for d, v in pts:
        if d.year == y and d.month == m and d != bmd:
            cf = cashflows.get((account_id, d), 0.0)
            cf_total += cf
            w = (days - (d - bmd).days) / days
            weighted += w * cf
    denom = bv + weighted
    if denom == 0:
        return None
    return (ev - bv - cf_total) / denom


def assets_correlation(cur, account_id):
    """Correlación media pairwise entre retornos diarios de los assets de la cuenta."""
    asset_ids = account_assets(cur, account_id)
    returns = {a: asset_daily_returns(cur, a) for a in asset_ids}
    returns = {a: r for a, r in returns.items() if len(r) >= 2}
    keys = list(returns)
    if len(keys) < 2:
        return None
    corrs = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            ra, rb = returns[keys[i]], returns[keys[j]]
            common = sorted(set(ra) & set(rb))
            if len(common) < 2:
                continue
            xa = [ra[d] for d in common]
            xb = [rb[d] for d in common]
            try:
                corrs.append(statistics.correlation(xa, xb))
            except (statistics.StatisticsError, ValueError):
                continue
    return sum(corrs) / len(corrs) if corrs else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="escribe en account_monthly_metrics (default: dry-run)")
    ap.add_argument("--clerk-id", default=None, help="acotar a las cuentas de un usuario")
    args = ap.parse_args()

    conn, cur = connection_bdd()
    series = build_value_series(cur)
    cashflows = build_cashflows(cur)
    scope = accounts_for_clerk(cur, args.clerk_id) if args.clerk_id else None

    rows = []  # (account_id, date, twr, dietz, sharpe_ratio, var, sortino, assets_correlation)
    print(f"{'account_id':38}{'fecha':>12}{'twr':>10}{'dietz':>10}{'sharpe':>9}{'sortino':>9}{'var':>14}{'corr':>8}")
    for account_id, pts in series.items():
        if scope is not None and account_id not in scope:
            continue
        if len(pts) < 2:
            continue
        daily = daily_adjusted_returns(pts, cashflows, account_id)
        monthly = monthly_returns(daily)
        if not monthly:
            continue
        t = twr(monthly)
        die = modified_dietz_last_month(pts, cashflows, account_id)
        sh = sharpe(monthly)
        so = sortino(monthly)
        v = var_amount(monthly, pts[-1][1])
        corr = assets_correlation(cur, account_id)
        last_date = pts[-1][0]
        rows.append((account_id, last_date, t, die, sh, v, so, corr))

        def f(x, p="{:>9.4f}"):
            return p.format(x) if x is not None else f"{'-':>9}"
        print(f"{account_id:38}{str(last_date):>12}{f(t,'{:>10.4f}')}{f(die,'{:>10.4f}')}"
              f"{f(sh)}{f(so)}{f(v,'{:>14,.2f}')}{f(corr,'{:>8.3f}')}")

    if not args.apply:
        print(f"\n  DRY-RUN: {len(rows)} cuentas calculadas, no se escribió nada. Usa --apply.")
        close_bdd(conn, cur)
        return 0

    account_ids = [r[0] for r in rows]
    if account_ids:
        cur.execute(
            "DELETE FROM account_monthly_metrics WHERE account_id = ANY(%s::uuid[])",
            (account_ids,),
        )
        # `id` no tiene default a nivel de BD → se genera acá.
        rows_with_id = [(str(uuid.uuid4()), *r) for r in rows]
        execute_values(
            cur,
            "INSERT INTO account_monthly_metrics "
            "(id, account_id, date, twr, dietz, sharpe_ratio, var, sortino, assets_correlation) "
            "VALUES %s",
            rows_with_id,
        )
        conn.commit()
    print(f"\n  ✅ {len(rows)} filas escritas en account_monthly_metrics.")
    close_bdd(conn, cur)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
