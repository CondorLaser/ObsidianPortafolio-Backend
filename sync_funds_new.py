import requests
import psycopg2
from psycopg2.extras import execute_values
from datetime import date, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://fintual.cl/api"

FINTUAL_REAL_ASSETS = {
    245:   ("APV", "Risky Norris"),
    186:   ("A",   "Risky Norris"),
    25894: ("A",   "Risky Chuck"),
    187:   ("A",   "Moderate Pitt"),
    246:   ("APV", "Moderate Pitt"),
    26172: ("A",   "Moderate Brad 107"),
    188:   ("A",   "Conservative Clooney"),
    247:   ("APV", "Conservative Clooney"),
    26174: ("A",   "Conservative George 107"),
    15077: ("A",   "Very Conservative Streep"),
}

DEFAULT_FROM = date(2025, 6, 10)  

def connection_bdd():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    return conn, cur

def close_bdd(conn, cur):
    cur.close()
    conn.close()


def get_or_create_asset(cur, symbol, name):
    cur.execute("SELECT id FROM assets WHERE symbol = %s AND name = %s", (symbol, name))
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute("""
        INSERT INTO assets (symbol, name, kind, currency)
        VALUES (%s, %s, 'fund', 'CLP')
        ON CONFLICT (symbol, name) DO NOTHING
        RETURNING id
    """, (symbol, name))
    row = cur.fetchone()
    if row:
        return row[0]

    # Si DO NOTHING se disparó, buscar el existente
    cur.execute("SELECT id FROM assets WHERE symbol = %s AND name = %s", (symbol, name))
    return cur.fetchone()[0]


def get_last_price_date(cur, asset_id):
    """Devuelve la última fecha con precio o None."""
    cur.execute("""
        SELECT MAX(date) FROM asset_prices WHERE asset_id = %s
    """, (asset_id,))
    row = cur.fetchone()
    return row[0] if row and row[0] else None


def fetch_fintual_prices(real_asset_id, from_date, to_date):
    """Llama a /real_assets/{id}/days y devuelve [(date, close), ...]"""
    url = f"{BASE_URL}/real_assets/{real_asset_id}/days"
    params = {
        "from_date": from_date.strftime("%Y-%m-%d"),
        "to_date":   to_date.strftime("%Y-%m-%d"),
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    data = resp.json().get("data", [])

    prices = []
    for item in data:
        attr = item["attributes"]
        prices.append((attr["date"], float(attr["price"])))
    return prices


# ── Main ──────────────────────────────────────────────────────────────────────
conn, cur = connection_bdd()
today = date.today()

for real_asset_id, (symbol, name) in FINTUAL_REAL_ASSETS.items():
    print(f"\nProcesando {name} (real_asset_id: {real_asset_id})")

    asset_id = get_or_create_asset(cur, symbol, name)
    conn.commit()

    last_date = get_last_price_date(cur, asset_id)
    if last_date:
        from_date = last_date + timedelta(days=1)
        print(f"  Último precio: {last_date} → pidiendo desde {from_date}")
    else:
        from_date = DEFAULT_FROM
        print(f"  Sin precios → pidiendo desde {from_date} (1 año atrás)")

    if from_date >= today:
        print("  Ya está al día, nada que actualizar.")
        continue

    prices = fetch_fintual_prices(real_asset_id, from_date, today)
    print(f"  Precios obtenidos: {len(prices)}")

    if not prices:
        continue

    rows = [(asset_id, d, close, "CLP", "fintual") for d, close in prices]
    execute_values(cur, """
        INSERT INTO asset_prices (asset_id, date, close, currency, source)
        VALUES %s
        ON CONFLICT (asset_id, date) DO UPDATE SET close = EXCLUDED.close
    """, rows)
    conn.commit()
    print(f" Insertados/actualizados: {len(rows)} precios")

close_bdd(conn, cur)
print("\n Sync Fintual completado")