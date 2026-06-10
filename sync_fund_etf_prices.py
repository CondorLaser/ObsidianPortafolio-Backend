import time
import os
import requests
import psycopg2
from datetime import datetime, timedelta
from psycopg2.extras import execute_values


BASE_URL = "https://fintual.cl/api"

def get_last_stored_date(cur):
   cur.execute(
      """
      SELECT MAX(ap.date)
      FROM asset_prices ap
      JOIN assets a ON a.id = ap.asset_id
      WHERE a.kind IN ('etf', 'fund')
      """,
   )
   return cur.fetchone()[0]


def get_conceptual_assets():
    resp = requests.get(f"{BASE_URL}/conceptual_assets", timeout=30)
    resp.raise_for_status()

    assets = []
    for item in resp.json().get("data", []):
        attrs = item.get("attributes", {})
        assets.append({
            "id":       item.get("id"),
            "name":     attrs.get("name"),
            "symbol":   attrs.get("symbol"),
            "kind":     attrs.get("category") or attrs.get("kind") or item.get("type"),
            "currency": attrs.get("currency"),
            "run":      attrs.get("run"),
            "provider": attrs.get("provider"),
        })
    return assets


def get_real_assets_for_conceptual(conceptual_asset_id, retries=5):
    for attempt in range(retries):
        try:
            resp = requests.get(f"{BASE_URL}/conceptual_assets/{conceptual_asset_id}/real_assets", timeout=30)
            resp.raise_for_status()
            return resp.json().get("data", [])
        except Exception as e:
            if "429" in str(e) and attempt < retries - 1:
                wait = 2 ** attempt * 20
                print(f"Rate limit, esperando {wait}s...")
                time.sleep(wait)
            else:
                print(f"Error en {conceptual_asset_id}: {e}")
                return []


def get_price_history(real_asset_id, from_date=None, to_date=None):
    if to_date is None:
        to_date = datetime.today().strftime("%Y-%m-%d")
    if from_date is None:
        from_date = (datetime.today() - timedelta(days=365)).strftime("%Y-%m-%d")

    resp = requests.get(
        f"{BASE_URL}/real_assets/{real_asset_id}/days",
        params={"from_date": from_date, "to_date": to_date},
        timeout=30,
    )
    resp.raise_for_status()

    rows = []
    for item in resp.json().get("data", []):
        attrs = item.get("attributes", {})
        rows.append({
            "date":         attrs.get("date"),
            "price":        attrs.get("price"),
            "nav":          attrs.get("nav"),
            "total_return": attrs.get("total_return"),
        })
    return rows


def get_price_history_safe(real_asset_id, from_date=None, to_date=None, retries=5):
    for attempt in range(retries):
        try:
            return get_price_history(real_asset_id, from_date, to_date)
        except Exception as e:
            if "429" in str(e) and attempt < retries - 1:
                wait = 2 ** attempt * 20
                print(f"Rate limit, esperando {wait}s...")
                time.sleep(wait)
            else:
                print(f"Error en {real_asset_id}: {e}")
                return []


# ── 1. Armar data de assets (sin BDD) ────────────────────────────────────────
assets = get_conceptual_assets()
usefull = []

for a in assets:
    if a["kind"] == "etf" or a["kind"] == "mutual_fund":
        usefull.append(a)

data = []
real_asset_map = {}  # conceptual_id → [(serie_symbol, ra_id), ...]

for asset in usefull:
    kind = "fund" if asset["kind"] == "mutual_fund" else "etf"

    if asset["kind"] == "mutual_fund":
        real_assets = get_real_assets_for_conceptual(asset["id"])
        for ra in real_assets:
            ra_attrs = ra.get("attributes", {})
            ra_serie  = ra_attrs.get("serie")   # "A", "APV", etc.
            data.append((
                ra_serie,        # symbol = serie, coincide con el PDF
                asset["name"],   # "Risky Norris"
                kind,
                asset["currency"],
            ))
            real_asset_map.setdefault(asset["id"], []).append((ra_serie, ra["id"]))
        time.sleep(1)
    else:
        data.append((
            asset["symbol"],
            asset["name"],
            kind,
            asset["currency"],
        ))

# ── 2. Insertar assets en BDD ─────────────────────────────────────────────────
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

query_assets = """
INSERT INTO assets (symbol, name, kind, currency)
VALUES %s
ON CONFLICT (symbol, name) DO NOTHING
"""
execute_values(cur, query_assets, data)
conn.commit()

# Ultima fecha del asset en particular
cur.execute("""
    SELECT a.id, MAX(ap.date) as ultima_fecha
    FROM assets a
    LEFT JOIN asset_prices ap ON ap.asset_id = a.id
    WHERE a.kind IN ('etf', 'fund')
    GROUP BY a.id
""")
last_date_by_asset = {row[0]: row[1] for row in cur.fetchall()}

cur.close()
conn.close()

# ── 3. Bajar precios de Fintual ───────────────────────────────────────────────
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()      

cur.execute("SELECT id, symbol, name, currency FROM assets")
rows = cur.fetchall()
symbol_name_to_id       = {(row[1], row[2]): row[0] for row in rows}
symbol_name_to_currency = {(row[1], row[2]): row[3] for row in rows}

cur.close()  
conn.close()

all_prices = {}

for i, asset in enumerate(usefull):
    if asset["kind"] == "mutual_fund":
        for ra_serie, ra_id in real_asset_map.get(asset["id"], []):
            asset_id_bdd = symbol_name_to_id.get((ra_serie, asset["name"]))
            asset_last_date = last_date_by_asset.get(asset_id_bdd)
            from_date = (asset_last_date + timedelta(days=1)).isoformat() if asset_last_date else "2020-01-01"
            prices = get_price_history_safe(ra_id, from_date)
            all_prices[(ra_serie, asset["name"])] = prices
    else:
        real_assets = get_real_assets_for_conceptual(asset["id"])
        if real_assets:
            asset_id_bdd = symbol_name_to_id.get((asset["symbol"], asset["name"]))
            asset_last_date = last_date_by_asset.get(asset_id_bdd)
            from_date = (asset_last_date + timedelta(days=1)).isoformat() if asset_last_date else "2020-01-01"
            prices = get_price_history_safe(real_assets[0]["id"], from_date)
            all_prices[(asset["symbol"], asset["name"])] = prices

    time.sleep(1)

    if i % 50 == 0:
        print(f"{i}/{len(usefull)} procesados...")

# ── 4. Insertar precios en BDD ────────────────────────────────────────────────
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()


price_data = []
for (symbol, name), prices in all_prices.items():
    asset_id = symbol_name_to_id.get((symbol, name))
    if not asset_id:
        continue
    for p in prices:
        price_data.append((
            asset_id,
            p["date"],
            p["price"],
            "fintual",
            symbol_name_to_currency.get((symbol, name))
        ))

query = """
INSERT INTO asset_prices (asset_id, date, close, source, currency)
VALUES %s
ON CONFLICT (asset_id, date) DO NOTHING
"""
execute_values(cur, query, price_data)

conn.commit()
cur.close()
conn.close()

print(f"Listo — {len(price_data)} precios insertados para {len(all_prices)} activos.")