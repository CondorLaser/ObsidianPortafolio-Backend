"""Matemática pura de las métricas a nivel de CUENTA — única fuente de verdad.

La usan DOS consumidores con loaders distintos pero el MISMO cálculo:
  - `scripts_ghactions/accounts_{daily,monthly}_metrics.py` (cron, psycopg2 sync).
  - `app/repositories/account_metrics_repo.py` (app, SQLAlchemy async, al subir PDF).

Reglas de diseño:
  - SOLO stdlib. El workflow del cron instala apenas `psycopg2-binary`, así que
    este módulo no puede importar SQLAlchemy/pydantic/config. Mantener así.
  - Funciones puras sobre listas/dicts ya cargados. El I/O vive en cada consumidor.

Retornos AJUSTADOS por flujo de caja:  r[d] = (V[d] - V[d-1] - CF[d]) / V[d-1]
de modo que aportes/rescates no se cuentan como rendimiento.
"""
import statistics
from collections import defaultdict
from math import sqrt

TRADING_DAYS = 252
MONTHS = 12

# Límite representable de las columnas Numeric(6,4) sharpe_ratio/sortino.
# (6 dígitos, 4 decimales -> parte entera de 2 dígitos -> máximo 99.9999).
SHARPE_SORTINO_MAX = 99.9999


def clamp(value, max_abs):
    """Acota `value` a [-max_abs, +max_abs]. None pasa como None.

    Usado en sharpe/sortino: cuando la dispersión es ínfima el ratio se dispara
    a miles (artefacto numérico de una cuenta con casi puros meses positivos) y
    no cabe en Numeric(6,4). En vez de anularlo (perder la señal "rinde muy
    bien"), lo topamos al máximo de la columna.
    """
    if value is None:
        return None
    if value > max_abs:
        return max_abs
    if value < -max_abs:
        return -max_abs
    return value


def fit(value, max_abs):
    """Devuelve None si `value` no cabe en su columna Numeric (data sucia).

    Para métricas donde topar no tiene sentido financiero (twr/dietz/var): si
    se sale de rango es más honesto anular que inventar un tope.
    """
    if value is None:
        return None
    if abs(value) >= max_abs:
        return None
    return value


# ── Retornos ────────────────────────────────────────────────────────────────
def daily_adjusted_returns(pts, cashflows, account_id):
    """[(date, r), ...] con r ajustado por el flujo de caja del día.

    `pts`: [(date, value), ...] asc.  `cashflows`: {(account_id, date): cf}.
    """
    out = []
    for i in range(1, len(pts)):
        prev_v = pts[i - 1][1]
        if prev_v == 0:
            continue
        d = pts[i][0]
        cf = cashflows.get((account_id, d), 0.0)
        out.append((d, (pts[i][1] - prev_v - cf) / prev_v))
    return out


def adjusted_returns(pts, cashflows, account_id):
    """Igual que `daily_adjusted_returns` pero solo la lista de r (sin fecha)."""
    return [r for _, r in daily_adjusted_returns(pts, cashflows, account_id)]


def monthly_returns(daily):
    """Encadena retornos diarios a mensuales (TWR): por mes Π(1+r)-1.
    `daily`: [(date, r), ...].  Devuelve [((year, month), ret), ...] asc."""
    prod = defaultdict(lambda: 1.0)
    for d, r in daily:
        prod[(d.year, d.month)] *= (1 + r)
    return [(k, v - 1.0) for k, v in sorted(prod.items())]


# ── Métricas diarias ──────────────────────────────────────────────────────────
def volatility(returns):
    r = returns[-TRADING_DAYS:]
    if len(r) < 2:
        return None
    return statistics.stdev(r) * sqrt(TRADING_DAYS)


def max_drawdown_twr(returns):
    """Drawdown (%) sobre el índice time-weighted (no contaminado por flujos)."""
    idx = 1.0
    peak = 1.0
    mdd = 0.0
    for r in returns:
        idx *= (1 + r)
        peak = max(peak, idx)
        mdd = min(mdd, (idx - peak) / peak * 100 if peak != 0 else 0.0)
    return mdd


# ── Métricas mensuales ────────────────────────────────────────────────────────
def twr(monthly):
    rets = [r for _, r in monthly][-MONTHS:]
    acc = 1.0
    for r in rets:
        acc *= (1 + r)
    return acc - 1.0


def sharpe(monthly):
    """(media / stdev) * sqrt(12), rf=0. Topado a ±SHARPE_SORTINO_MAX.

    None solo si no hay señal: <2 retornos, o dispersión 0 con media 0.
    Si la dispersión es 0 pero la media no, el ratio es ±∞ -> tope ±max.
    """
    rets = [r for _, r in monthly]
    if len(rets) < 2:
        return None
    mean = statistics.mean(rets)
    sd = statistics.stdev(rets)
    if sd == 0:
        if mean == 0:
            return None
        return clamp(mean * float("inf"), SHARPE_SORTINO_MAX)
    return clamp((mean / sd) * sqrt(MONTHS), SHARPE_SORTINO_MAX)


def sortino(monthly):
    """(media / downside dev) * sqrt(12), rf=0. Topado a ±SHARPE_SORTINO_MAX.

    Mismo criterio que `sharpe`: una cuenta con casi puros meses positivos tiene
    downside ≈ 0 y el ratio se dispara a miles -> lo topamos en vez de anularlo.
    None solo si no hay señal (data insuficiente o serie plana sin rendimiento).
    """
    rets = [r for _, r in monthly]
    if len(rets) < 2:
        return None
    mean = statistics.mean(rets)
    downside = sqrt(sum(min(r, 0.0) ** 2 for r in rets) / len(rets))
    if downside == 0:
        if mean == 0:
            return None
        return clamp(mean * float("inf"), SHARPE_SORTINO_MAX)
    return clamp((mean / downside) * sqrt(MONTHS), SHARPE_SORTINO_MAX)


def var_amount(monthly, current_value):
    """VaR histórico: |percentil 5% de retornos mensuales| * valor actual."""
    rets = sorted(r for _, r in monthly)
    if len(rets) < 2 or current_value is None:
        return None
    idx = max(0, int(0.05 * len(rets)) - 1) if len(rets) >= 20 else 0
    p5 = rets[idx]
    return abs(min(p5, 0.0)) * float(current_value)


def modified_dietz_last_month(pts, cashflows, account_id):
    """Modified Dietz del último mes presente en la serie `pts`."""
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


def mean_pairwise_correlation(returns_by_asset):
    """Correlación media pairwise entre retornos diarios de los assets.

    `returns_by_asset`: {asset_id: {date: ret}}. Devuelve None si hay <2 assets
    con suficiente historia común.
    """
    returns = {a: r for a, r in returns_by_asset.items() if len(r) >= 2}
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
