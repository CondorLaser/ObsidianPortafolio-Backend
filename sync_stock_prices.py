import os
import time
import requests
import psycopg2
import pandas as pd
from datetime import datetime, timedelta
from psycopg2.extras import execute_values


TWELVEDATA_URL = "https://api.twelvedata.com/time_series"

base_params = {
    "interval": "1day",
    "outputsize": 5000,
    "apikey": os.environ["TWELVEDATA_API_KEY"],
}




def get_last_stored_date(cur, asset_id: int):
    cur.execute("SELECT MAX(date) FROM asset_price WHERE asset_id = %s", (asset_id,))
    return cur.fetchone()[0]


def build_request_params(base_params: dict, symbol: str, last_date) -> dict:
    params = base_params.copy()
    params["symbol"] = symbol
    if last_date:
        params["start_date"] = (last_date + timedelta(days=1)).isoformat()
    return params


def fetch_prices(url: str, params: dict) -> list[dict] | None: #buscar en twelvedata
    response = requests.get(url, params=params)
    data = response.json()
    if "values" not in data:
        print(f"  ✗ Error en la API: {data}")
        return None
    return data["values"]


def parse_price_rows(values: list[dict], asset_id: int) -> list[tuple]:  #cambia el formato para poder subirlo a la bdd
    return [
        (asset_id, datetime.strptime(row["datetime"], "%Y-%m-%d").date(), float(row["close"]), "twelvedata", "USD")
        for row in values
    ]


def upload_neon(cur, conn, price_data: list[tuple]): #sube a la bdd
    execute_values(
        cur,
        """
        INSERT INTO asset_price (asset_id, date, close, source, currency)
        VALUES %s
        ON CONFLICT (asset_id, date) DO NOTHING
        """,
        price_data,
    )
    conn.commit()


def sync_symbol(cur, conn, symbol: str, asset_id: int):
    last_date = get_last_stored_date(cur, asset_id)
    params = build_request_params(base_params, symbol, last_date)

    values = fetch_prices(TWELVEDATA_URL, params)
    if values is None:
        return False

    price_data = parse_price_rows(values, asset_id)

    if price_data:
        upload_neon(cur, conn, price_data)
        print(f" {len(price_data)} registros guardados")
    else:
        print(f" Sin datos nuevos")

    return True


conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()
cur.execute("SELECT id, symbol FROM asset WHERE kind = 'stock'") #solo las acciones NO ETF NI FONDOS MUTUOS
symbol_to_id = {symbol: id for id, symbol in cur.fetchall()}

for i, (symbol, asset_id) in enumerate(symbol_to_id.items()):
    print(f"[{i + 1}/{len(symbol_to_id)}] {symbol}")

    ok = sync_symbol(cur, conn, symbol, asset_id)
    if not ok:
        break

    time.sleep(8)

cur.close()
conn.close()