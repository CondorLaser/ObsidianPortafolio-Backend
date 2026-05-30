import os
import subprocess
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
load_dotenv()

# ── 1. Apuntar DATABASE_URL a testing ────────────────────────────────────────
os.environ["DATABASE_URL"] = os.environ["DATABASE_TESTING"]

conn = psycopg2.connect(os.environ["DATABASE_TESTING"])
cur = conn.cursor()

# ── 2. Insertar datos de prueba ───────────────────────────────────────────────
cur.execute("""
    INSERT INTO assets (symbol, name, kind, currency)
    VALUES ('TEST-ASSET-001', '[TEST] Asset de prueba', 'etf', 'USD')
    ON CONFLICT (symbol, name) DO NOTHING
    RETURNING id
""")
row = cur.fetchone()
if row is None:
    cur.execute("SELECT id FROM assets WHERE symbol = 'TEST-ASSET-001'")
    row = cur.fetchone()
asset_id = row[0]

test_prices = [
    (asset_id, '2024-01-01', 100, 'test', 'USD'),
    (asset_id, '2024-01-02', 200, 'test', 'USD'),
    (asset_id, '2024-01-03', 150, 'test', 'USD'),
    (asset_id, '2024-01-04', 200, 'test', 'USD'),
    (asset_id, '2024-01-05', 100, 'test', 'USD'),
]
execute_values(cur, """
    INSERT INTO asset_prices (asset_id, date, close, source, currency)
    VALUES %s
    ON CONFLICT (asset_id, date) DO NOTHING
""", test_prices)
conn.commit()

# ── 3. Correr el script real ──────────────────────────────────────────────────
result = subprocess.run(
    ["python", "scripts_ghactions/assets_daily_metrics.py"],
    capture_output=True,
    text=True
)
print(result.stdout)
if result.returncode != 0:
    print(result.stderr)
    raise Exception("SCRIPT FAILED")

# ── 4. Verificar resultados en la BDD ────────────────────────────────────────
cur.execute("""
    SELECT absolute_return, volatility, max_drawdown
    FROM asset_daily_metrics
    WHERE asset_id = %s
    ORDER BY date DESC
    LIMIT 1
""", (asset_id,))
row = cur.fetchone()
absolute_return, volatility, max_drawdown = float(row[0]), float(row[1]), float(row[2])

print("\n── TEST 1: Absolute Return ──")
print(f"  Resultado: {absolute_return:.2f}%  Esperado: 0.00%")
assert abs(absolute_return - 0.0) < 0.01, f"FALLÓ: {absolute_return}"
print("PASSED")

print("\n── TEST 2: Volatility ──")
print(f"  Resultado: {volatility:.6f}  (debe ser > 0)")
assert volatility > 0, f"FALLÓ: {volatility}"
print("PASSED")

print("\n── TEST 3: Max Drawdown ──")
print(f"  Resultado: {max_drawdown:.2f}%  Esperado: -50.00%")
assert abs(max_drawdown - (-50.0)) < 0.01, f"FALLÓ: {max_drawdown}"
print("PASSED")

# ── 5. Teardown ───────────────────────────────────────────────────────────────
cur.execute("DELETE FROM asset_prices WHERE asset_id = %s", (asset_id,))
cur.execute("DELETE FROM asset_daily_metrics WHERE asset_id = %s", (asset_id,))
cur.execute("DELETE FROM assets WHERE id = %s", (asset_id,))
conn.commit()
cur.close()
conn.close()
print("\nALL CHECKS PASSED")