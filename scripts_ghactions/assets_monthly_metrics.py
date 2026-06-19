from math import sqrt
from collections import defaultdict
import os
import psycopg2
from psycopg2.extras import execute_values
import requests


#ACA HACEMOS EL UPDATE DE LAS MÉTRICAS MENSUALES DE LOS ASSETS   
def connection_bdd():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    return conn, cur

def close_bdd(conn, cur):
    cur.close()
    conn.close()


print("Comenzamos Beta")    

#vamos a buscar las baselines:
BASELINE_FONDOS_MUTUOS = "bfc18ef3-8ce1-4faf-bcb9-df78524622c4"  # IPSA
BASELINE_ETF_ACCIONES  = "5e65fe42-49fc-4b8c-ab3f-7562437518af"  # SPY

def get_prices(cur, asset_id, limit=None):
    """Devuelve [(date, close), ...] ordenado ASC para un asset."""
    if limit:
        cur.execute("""
            SELECT date, close
            FROM (
                SELECT date, close,
                       ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY date DESC) AS rn
                FROM asset_prices
                WHERE asset_id = %s
            ) t
            WHERE rn <= %s
            ORDER BY date ASC
        """, (asset_id, limit))
    else:
        cur.execute("""
            SELECT date, close
            FROM asset_prices
            WHERE asset_id = %s
            ORDER BY date ASC
        """, (asset_id,))
    return [(row[0], float(row[1])) for row in cur.fetchall()]


def prices_to_returns(prices):
    """Convierte [(date, close), ...] en {date: retorno_diario}."""
    returns = {}
    for i in range(1, len(prices)):
        prev_close = prices[i-1][1]
        if prev_close == 0:
            continue
        date = prices[i][0]
        daily_return = (prices[i][1] - prev_close) / prev_close
        returns[date] = daily_return
    return returns


def calculate_beta(returns_asset: dict, returns_mercado: dict) -> float | None:
    """
    Beta = Cov(Ra, Rm) / Var(Rm)
    Solo usa fechas donde ambos tienen retorno (inner join por fecha).
    """
    fechas_comunes = sorted(set(returns_asset) & set(returns_mercado))
    if len(fechas_comunes) < 30:  # mínimo 30 observaciones
        return None

    ra = [returns_asset[f]   for f in fechas_comunes]
    rm = [returns_mercado[f] for f in fechas_comunes]

    mean_ra = sum(ra) / len(ra)
    mean_rm = sum(rm) / len(rm)

    cov = sum((a - mean_ra) * (m - mean_rm) for a, m in zip(ra, rm)) / (len(ra) - 1)
    var = sum((m - mean_rm) ** 2               for m in rm)            / (len(rm) - 1)

    if var == 0:
        return None

    return cov / var

conn, cur = connection_bdd()

# Cargar baselines una sola vez
prices_ipsa = get_prices(cur, BASELINE_FONDOS_MUTUOS)
prices_spy  = get_prices(cur, BASELINE_ETF_ACCIONES)

returns_ipsa = prices_to_returns(prices_ipsa)
returns_spy  = prices_to_returns(prices_spy)

# Justo después de calcular returns_spy
retornos_lista = sorted(returns_spy.values())
print("SPY retornos más extremos:")
print("  Mayores:", retornos_lista[-5:])
print("  Menores:", retornos_lista[:5])

# Ver qué fechas tienen esos retornos extremos
for fecha, ret in returns_spy.items():
    if abs(ret) > 0.05:  # más de 5% en un día
        print(f"  OUTLIER: {fecha} → {ret:.4f}")

# Traer todos los assets (últimos 253 precios → 252 retornos)
cur.execute("""
    SELECT asset_id, date, close
    FROM (
        SELECT asset_id, date, close,
               ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY date DESC) AS rn
        FROM asset_prices
        WHERE asset_id NOT IN (%s, %s)
    ) t
    WHERE rn <= 253
    ORDER BY asset_id, date ASC
""", (BASELINE_FONDOS_MUTUOS, BASELINE_ETF_ACCIONES))

prices_by_asset = defaultdict(list)
for asset_id, date, close in cur.fetchall():
    prices_by_asset[asset_id].append((date, float(close)))

#traer tipo de cada asset
cur.execute("SELECT id, kind FROM assets")
asset_kinds = {row[0]: row[1] for row in cur.fetchall()}

#calcular beta 
info_beta = []
for asset_id, prices in prices_by_asset.items():
    asset_kind = asset_kinds.get(asset_id)
    returns_mercado = returns_ipsa if asset_kind == "fund" else returns_spy
    returns_asset = prices_to_returns(prices)

    #fechas_comunes = sorted(set(returns_asset) & set(returns_mercado))
    #print(f"{asset_id[:8]} | tipo={asset_kind} | fechas_asset={len(returns_asset)} | fechas_mercado={len(returns_mercado)} | fechas_comunes={len(fechas_comunes)}")
    
    # Fechas del IPSA
    #print("Tipo fecha IPSA:", type(list(returns_ipsa.keys())[0]), "| Ejemplo:", list(returns_ipsa.keys())[0])

    # Fechas de un fund cualquiera
    #un_fund_id = next(aid for aid, prices in prices_by_asset.items() if asset_types.get(aid) == "fund")
    #returns_fund = prices_to_returns(prices_by_asset[un_fund_id])
    #print("Tipo fecha fund:", type(list(returns_fund.keys())[0]), "| Ejemplo:", list(returns_fund.keys())[0])

    # Busca un stock conocido

    beta = calculate_beta(returns_asset, returns_mercado)

    if beta is None:
        continue

    last_date = prices[-1][0]
    info_beta.append((asset_id, last_date, float(beta)))

print(len(info_beta))
execute_values(
    cur,
    """
    INSERT INTO asset_monthly_metrics (asset_id, date, beta)
    VALUES %s
    ON CONFLICT (asset_id, date) DO UPDATE SET beta = EXCLUDED.beta
    """,
    info_beta,
)
conn.commit()
close_bdd(conn, cur)
