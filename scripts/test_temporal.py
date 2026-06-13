"""
Test temporal para warnings_module.py usando SQLite en memoria.

NOTA: Postgres usa %s y ANY(%s) para arrays; SQLite usa ? y no soporta ANY.
Este script "traduce" las queries sobre la marcha con un cursor wrapper,
solo para poder probar la LOGICA sin tocar la BDD real.
Cuando se use en producción (Postgres real), warnings_module.py se usa tal cual,
sin este wrapper.
"""

import sqlite3
import json
import re


class CursorWrapper:
    """Traduce %s -> ? y ANY(%s) -> placeholders IN (...) para poder testear en SQLite."""

    def __init__(self, real_cursor):
        self._cur = real_cursor

    def execute(self, query, params=()):
        new_params = []

        parts = re.split(r"%s", query)
        rebuilt = parts[0]
        for part, param in zip(parts[1:], params):
            if isinstance(param, list):
                if len(param) == 0:
                    placeholders = "NULL"
                else:
                    placeholders = ",".join("?" for _ in param)
                    new_params.extend(param)

                stripped = rebuilt.rstrip()
                if stripped.endswith("ANY("):
                    stripped = stripped[: -len("ANY(")].rstrip()
                    if stripped.endswith("="):
                        stripped = stripped[:-1].rstrip()
                    rebuilt = stripped + " IN (" + placeholders + ")"
                    part = part[1:] if part.startswith(")") else part
                else:
                    rebuilt += "(" + placeholders + ")"
                rebuilt += part
            else:
                rebuilt += "?" + part
                new_params.append(param)

        self._cur.execute(rebuilt, new_params)

    def fetchall(self):
        rows = self._cur.fetchall()
        return [tuple(_maybe_json(v) for v in row) for row in rows]

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        return tuple(_maybe_json(v) for v in row)


def _maybe_json(value):
    if isinstance(value, str) and value.startswith("{"):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return value
    return value


# --- Setup de BDD dummy ---

raw_conn = sqlite3.connect(":memory:")
raw_cur = raw_conn.cursor()

raw_cur.executescript("""
CREATE TABLE accounts (id TEXT, user_id TEXT, name TEXT);
CREATE TABLE user_preferences (
    user_id TEXT,
    pnl_percentage_account_daily REAL,
    pnl_percentage_asset_daily REAL,
    max_drawdown_portfolio_daily REAL,
    max_drawdown_account_daily REAL,
    asset_weight_weekly REAL
);
CREATE TABLE account_daily_metrics (account_id TEXT, date TEXT, pnl REAL, max_drawdown REAL);
CREATE TABLE portfolio_snapshots (
    id TEXT, user_id TEXT, date TEXT, total_value REAL,
    breakdown_by_currency TEXT, breakdown_by_account TEXT
);
CREATE TABLE portfolio_daily_metrics (portfolio_id TEXT, date TEXT, max_drawdown REAL, fx_decomposition TEXT);
CREATE TABLE positions (id TEXT, account_id TEXT, asset_id TEXT, quantity REAL);
CREATE TABLE position_daily_metrics (position_id TEXT, date TEXT, pnl REAL);
CREATE TABLE assets (id TEXT, symbol TEXT, name TEXT);
CREATE TABLE asset_prices (asset_id TEXT, date TEXT, close REAL);
CREATE TABLE profiles (clerk_id TEXT, email TEXT);
""")

USER_ID = "user_1"
ACCOUNT_ID = "acc_1"
SNAPSHOT_ID = "snap_2"  # snapshot mas reciente
ASSET_BTC = "asset_btc"
ASSET_ETH = "asset_eth"
POSITION_BTC = "pos_btc"
POSITION_ETH = "pos_eth"
EMAIL = "fschiappacasse@uc.cl"

raw_cur.execute("INSERT INTO accounts VALUES (?, ?, ?)", (ACCOUNT_ID, USER_ID, "Cuenta Principal"))

# Preferencias: 10%, 8%, 7%, 14%, 35% (escala 0-1: 0.10, 0.08, etc.)
raw_cur.execute("""
    INSERT INTO user_preferences VALUES (?, ?, ?, ?, ?, ?)
""", (USER_ID, 0.10, 0.08, 0.07, 0.14, 0.35))

# account_daily_metrics: pnl en $ (1500), drawdown excede umbral (20% > 14%)
raw_cur.execute("INSERT INTO account_daily_metrics VALUES (?, ?, ?, ?)",
                (ACCOUNT_ID, "2026-06-12", 1500, 0.20))

# portfolio_snapshots: dos fechas
# Ayer (snap_1): total_value=9000, breakdown_by_account: cuenta valia 9000
# hoy snap_2
raw_cur.execute("INSERT INTO portfolio_snapshots VALUES (?, ?, ?, ?, ?, ?)",
                (SNAPSHOT_ID, USER_ID, "2026-06-12", 12600,  # <-- era 10000
                 json.dumps({"USD": 2500}), json.dumps({ACCOUNT_ID: 12600})))
raw_cur.execute("INSERT INTO portfolio_snapshots VALUES (?, ?, ?, ?, ?, ?)",
                (SNAPSHOT_ID, USER_ID, "2026-06-12", 10000,
                 json.dumps({"USD": 2500}), json.dumps({ACCOUNT_ID: 10000})))
# P&L cuenta esperado: pnl_pct = 1500 / 9000 = 16.7% > 10% -> warning

# portfolio_daily_metrics: max_drawdown del portfolio = 10% (> 7% umbral) -> warning
# fx_decomposition se deja insertado pero NO se usa (alerta FX eliminada)
raw_cur.execute("INSERT INTO portfolio_daily_metrics VALUES (?, ?, ?, ?)",
                (SNAPSHOT_ID, "2026-06-12", 0.10, json.dumps({"USD": 2500})))

# assets
raw_cur.execute("INSERT INTO assets VALUES (?, ?, ?)", (ASSET_BTC, "BTC", "Bitcoin"))
raw_cur.execute("INSERT INTO assets VALUES (?, ?, ?)", (ASSET_ETH, "ETH", "Ethereum"))

# positions: BTC y ETH
raw_cur.execute("INSERT INTO positions VALUES (?, ?, ?, ?)", (POSITION_BTC, ACCOUNT_ID, ASSET_BTC, 0.1))
raw_cur.execute("INSERT INTO positions VALUES (?, ?, ?, ?)", (POSITION_ETH, ACCOUNT_ID, ASSET_ETH, 2.0))

# asset_prices: BTC subio de 60000 -> 66000, ETH se mantuvo 3000 -> 3000
raw_cur.execute("INSERT INTO asset_prices VALUES (?, ?, ?)", (ASSET_BTC, "2026-06-11", 60000))
raw_cur.execute("INSERT INTO asset_prices VALUES (?, ?, ?)", (ASSET_BTC, "2026-06-12", 66000))
raw_cur.execute("INSERT INTO asset_prices VALUES (?, ?, ?)", (ASSET_ETH, "2026-06-11", 3000))
raw_cur.execute("INSERT INTO asset_prices VALUES (?, ?, ?)", (ASSET_ETH, "2026-06-12", 3000))

# position_daily_metrics: pnl en $ para cada posicion (fecha mas reciente)
# BTC: valor_ayer = 0.1 * 60000 = 6000. pnl=900 -> pnl_pct = 900/6000 = 15% > 8% -> warning
# ETH: valor_ayer = 2.0 * 3000 = 6000. pnl=120  -> pnl_pct = 120/6000  = 2%  < 8% -> sin warning
raw_cur.execute("INSERT INTO position_daily_metrics VALUES (?, ?, ?)", (POSITION_BTC, "2026-06-12", 900))
raw_cur.execute("INSERT INTO position_daily_metrics VALUES (?, ?, ?)", (POSITION_ETH, "2026-06-12", 120))

# Concentracion esperada (total_value = 10000):
# BTC: 0.1 * 66000 = 6600 / 10000 = 66% > 35% -> warning
# ETH: 2.0 * 3000  = 6000 / 10000 = 60% > 35% -> warning

# Perfil: email asociado al clerk_id
raw_cur.execute("INSERT INTO profiles VALUES (?, ?)", (USER_ID, EMAIL))

raw_conn.commit()


# --- Conexion fake para warnings_module ---

def connection_bdd():
    return raw_conn, CursorWrapper(raw_cur)


def close_bdd(conn, cur):
    pass  # no cerramos la conexion real durante el test


# Inyectar las funciones de conexion en el modulo bajo test
import warnings_module
warnings_module.connection_bdd = connection_bdd
warnings_module.close_bdd = close_bdd

# Para no enviar mails reales durante este test, comentar la siguiente linea
# si no se quiere disparar inmmediate_mail (requiere SENDGRID_API_KEY):
# warnings_module.send_mails = lambda email, w: print(f"[mock] mail a {email} con {len(w)} alertas")

result = warnings_module.warnings(USER_ID)

print("Warnings encontradas:")
for w in result:
    print(" ", w)

print()
print(f"Total: {len(result)}")

found_types = set(w[0] for w in result)
print()
print("Tipos encontrados:", found_types)

# --- Verificaciones esperadas ---
expected_types = {
    "P&L account",     # 16.7% > 10%
    "max_drawdown",    # account 20% > 14% Y portfolio 10% > 7%
    "P&L asset",       # BTC 15% > 8%
    "asset_weight",    # BTC 66% y ETH 60%, ambos > 35%
}
print("Esperados:", expected_types)
print("FX eliminado: no debería aparecer 'fx_decomposition'")