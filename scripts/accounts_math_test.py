"""Unit tests (sin BD) de la matemática de métricas de cuenta.

Foco: el fix del sortino/sharpe NULL reportado por Florencia. Una cuenta con casi
puros meses positivos tiene downside ≈ 0 y el ratio se dispara a miles (~5452);
antes `_fit` lo dejaba NULL. Ahora `app.metrics.accounts` lo topa a ±99.9999
(máximo de la columna Numeric(6,4)).
"""
import statistics
from math import sqrt

import pytest

from app.metrics.accounts import (
    SHARPE_SORTINO_MAX,
    clamp,
    fit,
    sharpe,
    sortino,
)


def _monthly(returns):
    """[(clave, ret), ...] como los produce monthly_returns()."""
    return [((2025, i + 1), r) for i, r in enumerate(returns)]


# ── clamp / fit ───────────────────────────────────────────────────────────────
def test_clamp_tops_huge_values():
    assert clamp(5452.0, SHARPE_SORTINO_MAX) == 99.9999
    assert clamp(-5452.0, SHARPE_SORTINO_MAX) == -99.9999


def test_clamp_passes_in_range_and_none():
    assert clamp(1.5, SHARPE_SORTINO_MAX) == 1.5
    assert clamp(-3.2, SHARPE_SORTINO_MAX) == -3.2
    assert clamp(None, SHARPE_SORTINO_MAX) is None


def test_fit_nulls_out_of_range_keeps_in_range():
    assert fit(5452.0, 100) is None
    assert fit(50.0, 100) == 50.0
    assert fit(None, 100) is None


# ── sortino ───────────────────────────────────────────────────────────────────
def test_sortino_florencia_case_clamps_instead_of_null():
    # 11 meses fuertemente positivos + 1 mes apenas negativo → downside ínfimo,
    # ratio del orden de miles. Debe quedar topado, NO NULL.
    returns = [0.05] * 11 + [-0.0001]
    result = sortino(_monthly(returns))
    assert result is not None
    assert result == 99.9999
    assert abs(result) < 100  # cabe en Numeric(6,4)


def test_sortino_all_positive_zero_downside_is_max():
    # Sin ningún mes negativo: downside == 0, media > 0 → +máximo.
    result = sortino(_monthly([0.01, 0.02, 0.03, 0.015]))
    assert result == 99.9999


def test_sortino_insufficient_data_is_none():
    assert sortino(_monthly([0.05])) is None
    assert sortino(_monthly([])) is None


def test_sortino_flat_series_is_none():
    # Serie plana (sin dispersión ni rendimiento) → genuinamente indefinido.
    assert sortino(_monthly([0.0, 0.0, 0.0])) is None


def test_sortino_normal_value_not_clamped():
    returns = [0.02, -0.01, 0.03, -0.02, 0.01, -0.005, 0.015, -0.012]
    result = sortino(_monthly(returns))
    assert result is not None
    assert abs(result) < SHARPE_SORTINO_MAX  # caso real no toca el tope


# ── sharpe (mismo criterio) ───────────────────────────────────────────────────
def test_sharpe_tiny_dispersion_clamps():
    # Retornos casi idénticos → stdev ínfimo → ratio enorme → topado.
    returns = [0.0500, 0.0501, 0.0499, 0.0500, 0.05005]
    result = sharpe(_monthly(returns))
    assert result is not None
    assert result == 99.9999


def test_sharpe_zero_dispersion_negative_mean_is_negative_max():
    # Todos iguales y negativos: stdev 0, media < 0 → -máximo.
    assert sharpe(_monthly([-0.03, -0.03, -0.03])) == -99.9999


def test_sharpe_normal_value_matches_formula_and_unclamped():
    returns = [0.02, -0.01, 0.03, -0.02, 0.01, 0.0, 0.015, -0.005]
    expected = (statistics.mean(returns) / statistics.stdev(returns)) * sqrt(12)
    result = sharpe(_monthly(returns))
    assert result == pytest.approx(expected)
    assert abs(result) < SHARPE_SORTINO_MAX


def test_sharpe_insufficient_data_is_none():
    assert sharpe(_monthly([0.05])) is None
