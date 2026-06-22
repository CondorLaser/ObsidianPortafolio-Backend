# tests/test_metrics.py

from decimal import Decimal
from datetime import datetime, date, timezone
from unittest.mock import MagicMock

import pytest

from app.metrics.portfolio import (
    calculate_pnl,
    calculate_max_drawdown,
    calculate_volatility,
    calculate_twr,
    calculate_var,
    calculate_portfolio_daily_metrics,
)
from app.metrics.positions import (
    calculate_unrealized_pnl,
    calculate_total_pnl,
    calculate_position_daily_metrics,
)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def make_position(
    quantity="10",
    avg_cost="100",
    realized_pnl="50",
    updated_at=None,
):
    """Crea un mock de PositionRead con los campos mínimos necesarios."""
    pos = MagicMock()
    pos.id = "pos-001"
    pos.quantity = Decimal(quantity)
    pos.avg_cost = Decimal(avg_cost)
    pos.realized_pnl = Decimal(realized_pnl)
    pos.updated_at = updated_at or datetime(2024, 6, 1, tzinfo=timezone.utc)
    return pos


def make_snapshot(total_value=None, realized_pnl=None, unrealized_pnl=None, date_val=None):
    """Crea un snapshot como dict (formato que usan las funciones de portfolio)."""
    return {
        "date": date_val or date(2024, 6, 1),
        "total_value": total_value or {},
        "realized_pnl": realized_pnl or {},
        "unrealized_pnl": unrealized_pnl or {},
    }


# ─────────────────────────────────────────────
# POSITIONS — calculate_unrealized_pnl
# ─────────────────────────────────────────────

def test_unrealized_pnl_ganancia():
    """Precio actual mayor al costo promedio → ganancia positiva."""
    pos = make_position(quantity="10", avg_cost="100")
    result = calculate_unrealized_pnl(pos, current_price=Decimal("120"))
    assert result == Decimal("200")  # (120 - 100) * 10


def test_unrealized_pnl_perdida():
    """Precio actual menor al costo promedio → pérdida (negativo)."""
    pos = make_position(quantity="10", avg_cost="100")
    result = calculate_unrealized_pnl(pos, current_price=Decimal("80"))
    assert result == Decimal("-200")  # (80 - 100) * 10


def test_unrealized_pnl_campos_none():
    """quantity y avg_cost None → trata como 0, resultado 0."""
    pos = make_position(quantity="0", avg_cost="0")
    pos.quantity = None
    pos.avg_cost = None
    result = calculate_unrealized_pnl(pos, current_price=Decimal("100"))
    assert result == Decimal("0")


# ─────────────────────────────────────────────
# POSITIONS — calculate_total_pnl
# ─────────────────────────────────────────────

def test_total_pnl_suma_realizado_y_no_realizado():
    """Total PnL = realized + unrealized correctamente sumados."""
    pos = make_position(quantity="10", avg_cost="100", realized_pnl="50")
    result = calculate_total_pnl(pos, current_price=Decimal("120"))
    # unrealized = 200, realized = 50 → total = 250
    assert result == Decimal("250")


def test_total_pnl_con_perdida_no_realizada():
    """Pérdida no realizada puede superar la ganancia realizada → total negativo."""
    pos = make_position(quantity="10", avg_cost="100", realized_pnl="10")
    result = calculate_total_pnl(pos, current_price=Decimal("50"))
    # unrealized = -500, realized = 10 → total = -490
    assert result == Decimal("-490")


# ─────────────────────────────────────────────
# POSITIONS — calculate_position_daily_metrics
# ─────────────────────────────────────────────

def test_position_daily_metrics_estructura():
    """El dict retornado tiene todas las claves esperadas con tipos correctos."""
    pos = make_position()
    result = calculate_position_daily_metrics(pos, current_price=Decimal("110"))
    assert result["position_id"] == "pos-001"
    assert result["date"] == date(2024, 6, 1)
    assert isinstance(result["unrealized_pnl"], Decimal)
    assert isinstance(result["total_pnl"], Decimal)


# ─────────────────────────────────────────────
# PORTFOLIO — calculate_pnl
# ─────────────────────────────────────────────

def test_pnl_calcula_diferencia_entre_snapshots():
    """PnL diario = (realized+unrealized) de hoy - (realized+unrealized) de ayer."""
    yesterday = make_snapshot(
        realized_pnl={"USD": "100"},
        unrealized_pnl={"USD": "200"},
    )
    today = make_snapshot(
        realized_pnl={"USD": "110"},
        unrealized_pnl={"USD": "220"},
    )
    result = calculate_pnl([yesterday, today])
    assert result["USD"] == "30"  # (110+220) - (100+200) = 30


def test_pnl_con_campos_none():
    """Si realized_pnl o unrealized_pnl son None, los trata como 0 sin romper."""
    yesterday = make_snapshot(realized_pnl=None, unrealized_pnl=None)
    today = make_snapshot(realized_pnl={"USD": "50"}, unrealized_pnl=None)
    result = calculate_pnl([yesterday, today])
    assert result["USD"] == "50"


def test_pnl_snapshot_unico_retorna_vacio():
    """Con menos de 2 snapshots no hay delta posible → dict vacío."""
    result = calculate_pnl([make_snapshot()])
    assert result == {}


# ─────────────────────────────────────────────
# PORTFOLIO — calculate_max_drawdown
# ─────────────────────────────────────────────

def test_max_drawdown_detecta_caida_desde_peak():
    """Detecta la mayor caída desde el valor máximo histórico."""
    snapshots = [
        make_snapshot(total_value={"USD": "1000"}),
        make_snapshot(total_value={"USD": "1200"}),  # nuevo peak
        make_snapshot(total_value={"USD": "900"}),   # caída desde 1200
    ]
    result = calculate_max_drawdown(snapshots)
    # drawdown = (900 - 1200) / 1200 = -0.25
    assert Decimal(result["USD"]) == Decimal("-0.25")


def test_max_drawdown_sin_caida():
    """Si el valor solo sube, el drawdown es 0."""
    snapshots = [
        make_snapshot(total_value={"USD": "100"}),
        make_snapshot(total_value={"USD": "200"}),
        make_snapshot(total_value={"USD": "300"}),
    ]
    result = calculate_max_drawdown(snapshots)
    assert Decimal(result["USD"]) == Decimal("0")


# ─────────────────────────────────────────────
# PORTFOLIO — calculate_volatility
# ─────────────────────────────────────────────

def test_volatility_retorna_cero_con_dos_puntos_iguales():
    """Con solo 2 snapshots idénticos, un único return → stdev no aplica → '0'."""
    s = make_snapshot(
        total_value={"USD": "1000"},
        realized_pnl={"USD": "0"},
        unrealized_pnl={"USD": "0"},
    )
    result = calculate_volatility([s, s])
    assert result.get("USD") == "0"


def test_volatility_filtra_capital_bajo_threshold():
    """Capital menor al threshold (1 USD) no debe generar una entrada de volatilidad."""
    s1 = make_snapshot(total_value={"USD": "0.5"}, realized_pnl={"USD": "0"}, unrealized_pnl={"USD": "0"})
    s2 = make_snapshot(total_value={"USD": "0.6"}, realized_pnl={"USD": "0"}, unrealized_pnl={"USD": "0"})
    result = calculate_volatility([s1, s2])
    assert "USD" not in result


def test_volatility_con_retornos_variados():
    """Con retornos variables, retorna un string numérico válido > 0."""
    snapshots = [
        make_snapshot(total_value={"USD": "1000"}, realized_pnl={"USD": "0"},   unrealized_pnl={"USD": "0"}),
        make_snapshot(total_value={"USD": "1050"}, realized_pnl={"USD": "30"},  unrealized_pnl={"USD": "20"}),
        make_snapshot(total_value={"USD": "980"},  realized_pnl={"USD": "10"},  unrealized_pnl={"USD": "-70"}),
        make_snapshot(total_value={"USD": "1100"}, realized_pnl={"USD": "50"},  unrealized_pnl={"USD": "50"}),
    ]
    result = calculate_volatility(snapshots)
    assert "USD" in result
    assert Decimal(result["USD"]) > Decimal("0")


# ─────────────────────────────────────────────
# PORTFOLIO — calculate_twr
# ─────────────────────────────────────────────

def test_twr_retorno_compuesto_positivo():
    """TWR acumula correctamente retornos positivos encadenados."""
    # +5% cada período → TWR = (1.05 * 1.05) - 1 = 0.1025
    snapshots = [
        make_snapshot(total_value={"USD": "1000"}, realized_pnl={"USD": "0"},  unrealized_pnl={"USD": "0"}),
        make_snapshot(total_value={"USD": "1050"}, realized_pnl={"USD": "50"}, unrealized_pnl={"USD": "0"}),
        make_snapshot(total_value={"USD": "1100"}, realized_pnl={"USD": "100"},unrealized_pnl={"USD": "0"}),
    ]
    result = calculate_twr(snapshots)
    assert "USD" in result
    twr = Decimal(result["USD"])
    assert twr > Decimal("0")


def test_twr_un_solo_snapshot_retorna_vacio():
    """Sin al menos 2 snapshots no hay período → dict vacío."""
    result = calculate_twr([make_snapshot()])
    assert result == {}


# ─────────────────────────────────────────────
# PORTFOLIO — calculate_var
# ─────────────────────────────────────────────

def test_var_toma_percentil_5_de_retornos():
    """VaR al 95% selecciona el peor retorno del 5% inferior.
    
    Con 20 retornos, percentile_index = int(0.05 * 20) = 1.
    Usamos una serie con múltiples pérdidas para que el índice 1 sea negativo.
    """
    snapshots = []
    # Serie con caídas claras: -20%, -10%, luego subidas
    values = [1000, 800, 900, 950, 1000, 1020, 1050, 1030, 1060, 1080,
              1100, 1090, 1120, 1150, 1130, 1160, 1180, 1200, 1210, 1230, 1250]
    for i, v in enumerate(values):
        s = MagicMock()
        s.total_value = {"USD": str(v)}
        s.date = date(2024, 1, i + 1)
        snapshots.append(s)

    result = calculate_var(snapshots)
    assert "USD" in result
    assert Decimal(result["USD"]) > Decimal("0")


def test_var_retorna_cero_con_un_solo_retorno():
    """Con solo 2 snapshots, hay 1 retorno → no alcanza para percentil útil → '0'."""
    s1, s2 = MagicMock(), MagicMock()
    s1.total_value = {"USD": "1000"}
    s2.total_value = {"USD": "1100"}
    result = calculate_var([s1, s2])
    assert result.get("USD") == "0"


# ─────────────────────────────────────────────
# PORTFOLIO — calculate_portfolio_daily_metrics
# ─────────────────────────────────────────────

def test_daily_metrics_vacio_retorna_estructura_nula():
    """Sin snapshots, retorna estructura con date=None y dicts vacíos."""
    result = calculate_portfolio_daily_metrics([])
    assert result["date"] is None
    assert result["pnl"] == {}
    assert result["max_drawdown"] == {}
    assert result["volatility"] == {}


def test_daily_metrics_retorna_todas_las_claves():
    """Con snapshots válidos, el dict tiene date, pnl, max_drawdown, volatility."""
    snapshots = [
        make_snapshot(total_value={"USD": "1000"}, realized_pnl={"USD": "0"}, unrealized_pnl={"USD": "0"}, date_val=date(2024, 6, 1)),
        make_snapshot(total_value={"USD": "1050"}, realized_pnl={"USD": "50"},unrealized_pnl={"USD": "0"}, date_val=date(2024, 6, 2)),
    ]
    result = calculate_portfolio_daily_metrics(snapshots)
    assert result["date"] == date(2024, 6, 2)
    assert "pnl" in result
    assert "max_drawdown" in result
    assert "volatility" in result