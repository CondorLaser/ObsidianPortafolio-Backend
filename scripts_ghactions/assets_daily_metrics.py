import statistics
from math import sqrt
from collections import defaultdict
import os
import psycopg2
from psycopg2.extras import execute_values
import requests


#ACA HACEMOS EL UPDATE DE LAS MÉTRICAS DIARIAS    

def connection_bdd():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    return conn, cur

def close_bdd(conn, cur):
    cur.close()
    conn.close()



# ABSOLUTE RETURN
print("Comenzamos absolute return")
conn, cur = connection_bdd()
# Primer precio de cada asset
cur.execute("""
    SELECT DISTINCT ON (asset_id) asset_id, close, date
    FROM asset_prices
    ORDER BY asset_id, date ASC
""")
first_prices = {row[0]: (row[1], row[2]) for row in cur.fetchall()}

# Último precio de cada asset
cur.execute("""
    SELECT DISTINCT ON (asset_id) asset_id, close, date
    FROM asset_prices
    ORDER BY asset_id, date DESC
""")
last_prices = {row[0]: (row[1], row[2]) for row in cur.fetchall()}

info_absolute_returns = []
for asset_id, (last_close, last_date) in last_prices.items():
    first_close, first_date  = first_prices[asset_id]
    if first_close == 0:
        continue
    absolute_return = (last_close - first_close) / first_close * 100
    info_absolute_returns.append((asset_id, last_date, float(absolute_return)))

print(len(info_absolute_returns))
execute_values(
    cur,
    """
    INSERT INTO asset_daily_metrics (asset_id, date, absolute_return)
    VALUES %s
    ON CONFLICT (asset_id, date) DO UPDATE SET absolute_return = EXCLUDED.absolute_return
    """,
    info_absolute_returns,
)
conn.commit()
close_bdd(conn, cur)


#  VOLATILITY
conn, cur = connection_bdd()

# 253 precios para 252 retornos (anual sin finde)
cur.execute("""
    SELECT asset_id, date, close
    FROM (
        SELECT asset_id, date, close,
               ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY date DESC) AS rn
        FROM asset_prices
    ) t
    WHERE rn <= 253
    ORDER BY asset_id, date ASC
""")

prices_by_asset = defaultdict(list) #diccionario con asser_id : [(date 1 precio1), (date2 precio2), ...]
for asset_id, date, close in cur.fetchall():
    prices_by_asset[asset_id].append((date, float(close)))

#retorno_dia = (precio_hoy - precio_ayer) / precio_ayer
daily_return_dict =defaultdict(list)  #diccionario con asset_id : [retorno_dia, retorno_dia, ..., retorno_dia30]
for asset in prices_by_asset:
    daily_return_list = []
    for i in range(len(prices_by_asset[asset]) - 1):
        daily_return = (prices_by_asset[asset][i+1][1] - prices_by_asset[asset][i][1]) / prices_by_asset[asset][i][1]
        daily_return_list.append(daily_return)
    daily_return_dict[asset] = daily_return_list

info_volatility = []
for asset_id, returns in daily_return_dict.items():
    if len(returns) < 2:
        continue
    volatility = statistics.stdev(returns)  #desciación estandar
    volatility = volatility * sqrt(252) # volatilidad anual
    last_date = prices_by_asset[asset_id][-1][0] 
    info_volatility.append((asset_id, last_date, float(volatility)))


conn, cur = connection_bdd()

print(len(info_volatility))
execute_values(
    cur,
    """
    INSERT INTO asset_daily_metrics (asset_id, date, volatility)
    VALUES %s
    ON CONFLICT (asset_id, date) DO UPDATE SET volatility = EXCLUDED.volatility
    """,
    info_volatility,
)
conn.commit()
close_bdd(conn, cur)



#  MAX DRAWDOWN
conn, cur = connection_bdd()
# necesito todo el historial
cur.execute("""
    SELECT asset_id, date, close
    FROM asset_prices
    ORDER BY asset_id, date ASC
""")
all_prices_by_asset = defaultdict(list)
for asset_id, date, close in cur.fetchall():
    all_prices_by_asset[asset_id].append((date, float(close)))

max_drawdowns = []
for asset_id, asset_tuple in all_prices_by_asset.items(): #itero sobre los items
    
    peak = asset_tuple[0][1]
    max_drawdown = 0

    for date, price in asset_tuple:
        if price > peak:
            peak = price

        if peak == 0:
            dd = 0    #evito dividir por 0   

        else:
            dd = (price - peak) / peak * 100

        if dd < max_drawdown:
            max_drawdown = dd
    max_drawdowns.append((asset_id, asset_tuple[-1][0] , max_drawdown))

print(len(max_drawdowns))
execute_values(
    cur,
    """
    INSERT INTO asset_daily_metrics (asset_id, date, max_drawdown)
    VALUES %s
    ON CONFLICT (asset_id, date) DO UPDATE SET max_drawdown = EXCLUDED.max_drawdown
    """,
    max_drawdowns,
)
conn.commit()
close_bdd(conn, cur)