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


def get_real_assets_for_conceptual(conceptual_asset_id):
    resp = requests.get(f"{BASE_URL}/conceptual_assets/{conceptual_asset_id}/real_assets", timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", [])


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


# ── 1. Armar data de assets y precios (sin BDD) ───────────────────────────────
assets = get_conceptual_assets()
usefull = []

for a in assets:
    if a["kind"] == "etf" or a["kind"] == "mutual_fund":
        usefull.append(a)

data = []
real_asset_map = {}  # ra_symbol → fintual real_asset id

for asset in usefull:
    kind = "fund" if asset["kind"] == "mutual_fund" else "etf"

    if asset["kind"] == "mutual_fund":
        real_assets = get_real_assets_for_conceptual(asset["id"])
        for ra in real_assets:
            ra_attrs = ra.get("attributes", {})
            ra_symbol = ra_attrs.get("symbol")
            ra_serie  = ra_attrs.get("serie")
            data.append((
                ra_symbol,
                asset["name"],
                kind,
                asset["currency"],
                ra_serie,
            ))
            real_asset_map[ra_symbol] = ra["id"]
        time.sleep(0.5)
    else:
        data.append((
            asset["symbol"],
            asset["name"],
            kind,
            asset["currency"],
            None,
        ))

# ── 2. Insertar assets en BDD ─────────────────────────────────────────────────
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

query_assets = """
INSERT INTO assets (symbol, name, kind, currency, serie)
VALUES %s
ON CONFLICT (symbol, name) DO NOTHING
"""
execute_values(cur, query_assets, data)
conn.commit()

last_date = get_last_stored_date(cur)
if last_date:
    last_date = (last_date + timedelta(days=1)).isoformat()

cur.close()
conn.close()

# ── 3. Bajar precios de Fintual ───────────────────────────────────────────────
all_prices = {}

for i, asset in enumerate(usefull):
    if asset["kind"] == "mutual_fund":
        for ra_symbol, ra_id in real_asset_map.items():
            if ra_symbol.startswith(asset["symbol"]):
                prices = get_price_history_safe(ra_id, last_date)
                all_prices[ra_symbol] = prices
    else:
        real_assets = get_real_assets_for_conceptual(asset["id"])
        if real_assets:
            prices = get_price_history_safe(real_assets[0]["id"], last_date)
            all_prices[asset["symbol"]] = prices

    time.sleep(1)

    if i % 50 == 0:
        print(f"{i}/{len(usefull)} procesados...")

# ── 4. Insertar precios en BDD ────────────────────────────────────────────────
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

cur.execute("SELECT id, symbol, currency FROM assets")
rows = cur.fetchall()
symbol_to_id       = {row[1]: row[0] for row in rows}
symbol_to_currency = {row[1]: row[2] for row in rows}

price_data = []
for symbol, prices in all_prices.items():
    asset_id = symbol_to_id.get(symbol)
    if not asset_id:
        continue
    for p in prices:
        price_data.append((
            asset_id,
            p["date"],
            p["price"],
            "fintual",
            symbol_to_currency.get(symbol)
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