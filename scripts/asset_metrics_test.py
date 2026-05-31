import os
import subprocess

import psycopg2
import pytest
from psycopg2.extras import execute_values


# ── Fixture: aísla DATABASE_URL solo para este módulo ────────────────────────
@pytest.fixture(autouse=True)
def use_testing_db(monkeypatch):
    testing_url = os.environ.get("DATABASE_TESTING")
    if not testing_url:
        pytest.skip("DATABASE_TESTING no está seteada — skipping test de métricas")
    monkeypatch.setenv("DATABASE_URL", testing_url)


# ── Fixture: setup y teardown de datos sintéticos ────────────────────────────
@pytest.fixture()
def metrics_asset():
    """
    Inserta un asset con 5 precios sintéticos conocidos.
    Hace teardown completo al finalizar, sin importar si el test falla.
    """
    conn = psycopg2.connect(os.environ["DATABASE_TESTING"])
    cur = conn.cursor()

    # Setup
    cur.execute("""
        INSERT INTO assets (symbol, name, kind, currency)
        VALUES ('_INTTEST_METRICS_001', '[_INTTEST_] Asset métricas', 'etf', 'USD')
        ON CONFLICT (symbol, name) DO NOTHING
        RETURNING id
    """)
    row = cur.fetchone()
    if row is None:
        cur.execute("SELECT id FROM assets WHERE symbol = '_INTTEST_METRICS_001'")
        row = cur.fetchone()
    asset_id = row[0]

    # Precios diseñados para resultados deterministas:
    #   absolute_return  = (100 - 100) / 100 = 0.00%   (inicio == fin)
    #   max_drawdown     = (100 - 200) / 200 = -50.00%  (pico 200 → valle 100)
    #   volatility       > 0                             (hay variación)
    test_prices = [
        (asset_id, "2024-01-01", 100, "test", "USD"),
        (asset_id, "2024-01-02", 200, "test", "USD"),
        (asset_id, "2024-01-03", 150, "test", "USD"),
        (asset_id, "2024-01-04", 200, "test", "USD"),
        (asset_id, "2024-01-05", 100, "test", "USD"),
    ]
    execute_values(
        cur,
        """
        INSERT INTO asset_prices (asset_id, date, close, source, currency)
        VALUES %s
        ON CONFLICT (asset_id, date) DO NOTHING
        """,
        test_prices,
    )
    conn.commit()

    yield asset_id  # el test recibe el id

    # Teardown — corre siempre, incluso si el test falla
    cur.execute("DELETE FROM asset_daily_metrics WHERE asset_id = %s", (asset_id,))
    cur.execute("DELETE FROM asset_prices WHERE asset_id = %s", (asset_id,))
    cur.execute("DELETE FROM assets WHERE id = %s", (asset_id,))
    conn.commit()
    cur.close()
    conn.close()


# ── Test principal ────────────────────────────────────────────────────────────
def test_daily_metrics(metrics_asset):
    asset_id = metrics_asset

    # Correr el script real como lo haría el GH Action
    result = subprocess.run(
        ["python", "scripts_ghactions/assets_daily_metrics.py"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"assets_daily_metrics.py falló con código {result.returncode}:\n{result.stderr}"
    )

    # Leer métricas generadas
    conn = psycopg2.connect(os.environ["DATABASE_TESTING"])
    cur = conn.cursor()
    cur.execute(
        """
        SELECT absolute_return, volatility, max_drawdown
        FROM asset_daily_metrics
        WHERE asset_id = %s
        ORDER BY date DESC
        LIMIT 1
        """,
        (asset_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    assert row is not None, "El script no generó ninguna fila en asset_daily_metrics"

    absolute_return = float(row[0])
    volatility      = float(row[1])
    max_drawdown    = float(row[2])

    assert abs(absolute_return - 0.0) < 0.01, (
        f"absolute_return esperado 0.00%, got {absolute_return:.4f}%"
    )
    assert volatility > 0, (
        f"volatility debe ser > 0, got {volatility}"
    )
    assert abs(max_drawdown - (-50.0)) < 0.01, (
        f"max_drawdown esperado -50.00%, got {max_drawdown:.4f}%"
    )