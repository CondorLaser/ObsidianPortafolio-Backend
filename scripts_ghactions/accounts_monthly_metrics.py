"""Métricas MENSUALES a nivel de CUENTA → account_monthly_metrics.

Por cuenta (una fila, "as of" la última fecha):
  - twr                = retorno time-weighted acumulado (trailing 12 meses)
  - dietz              = Modified Dietz del último mes
  - sharpe_ratio       = (media ret. mensual / stdev) * sqrt(12)        (rf=0)
  - sortino            = (media ret. mensual / downside dev) * sqrt(12) (rf=0)
  - var                = |percentil 5% de retornos mensuales| * valor actual (CLP/USD)
  - assets_correlation = correlación media pairwise entre los assets de la cuenta

La MATEMÁTICA vive en `app.metrics.accounts` (única fuente de verdad, solo stdlib),
compartida con el cómputo app-side al subir PDF. Acá quedan solo los loaders
(psycopg2) y el I/O. sharpe/sortino vienen topados a ±99.9999 desde el módulo
(cuentas con downside ≈0 ya no salen NULL); twr/dietz/var se anulan vía `fit`
si la data sucia los saca de rango.

Upsert idempotente: DELETE de las cuentas tocadas + INSERT.

Uso:
    DATABASE_URL='postgresql://...neon...' python scripts_ghactions/accounts_monthly_metrics.py            # dry-run
    DATABASE_URL='postgresql://...neon...' python scripts_ghactions/accounts_monthly_metrics.py --apply --clerk-id X
"""
import argparse
import os
import sys
import uuid
from collections import defaultdict

import psycopg2
from psycopg2.extras import execute_values

# El cron corre `python scripts_ghactions/accounts_monthly_metrics.py` (script-mode),
# así que el repo root no está en sys.path: lo agregamos para poder importar `app`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.metrics.accounts import (
    daily_adjusted_returns,
    fit,
    mean_pairwise_correlation,
    modified_dietz_last_month,
    monthly_returns,
    sharpe,
    sortino,
    twr,
    var_amount,
)


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


def assets_correlation(cur, account_id):
    """Correlación media pairwise entre retornos diarios de los assets de la cuenta."""
    asset_ids = account_assets(cur, account_id)
    returns_by_asset = {a: asset_daily_returns(cur, a) for a in asset_ids}
    return mean_pairwise_correlation(returns_by_asset)


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
        # twr/dietz(10,8) y var(18,2)/corr(5,4) se anulan si no caben (fit).
        # sharpe/sortino(6,4) ya vienen topados a ±99.9999 desde el módulo.
        rows.append((
            account_id, last_date,
            fit(t, 100),
            fit(die, 100),
            sh,
            fit(v, 1e16),
            so,
            fit(corr, 10),
        ))

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
