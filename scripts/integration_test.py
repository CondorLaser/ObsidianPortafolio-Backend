"""Suite de pruebas integral del backend.

Cubre Fases 1-4 del plan de pruebas (capa de datos, API contract, webhook svix,
isolation entre usuarios). No requiere JWT real de Clerk — usa repos directos
para el isolation y el HTTP layer solo para validar wiring + shapes.

Uso:
    # Contra Docker local (asume `docker compose up` corriendo):
    ./venv/bin/python -m scripts.integration_test

    # Contra Neon develop:
    APP_ENV=prod DATABASE_URL='postgresql+asyncpg://...neon...' \\
        ./venv/bin/python -m scripts.integration_test --label=neon

Flags:
    --api-url URL    HTTP base de la API (default http://127.0.0.1:8000)
    --label NAME     etiqueta para el reporte (default 'local')
    --no-cleanup     no borra la data de test al terminar
"""
import argparse
import asyncio
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select, delete
from svix.webhooks import Webhook

from app.core.db import SessionLocal
from app.models.account import Account
from app.models.asset import Asset, AssetKind
from app.models.dividend import Dividend
from app.models.transaction import Transaction, TransactionKind
from app.models.user import Profile, RiskProfile
from app.models.user_preference import UserPreference
from app.repositories import (
    account_repo,
    asset_repo,
    dividend_repo,
    user_preference_repo,
    user_repo,
)
from app.schemas.account import AccountCreate
from app.schemas.asset import AssetCreate
from app.schemas.asset_price import AssetPriceCreate
from app.schemas.transaction import TransactionCreate
from app.schemas.user_preference import UserPreferenceUpdate
from app.repositories import asset_price_repo


# ────────────────────────────────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────────────────────────────────
TEST_USER_PREFIX = "_inttest_"  # data de test se borra al final
WEBHOOK_SECRET = "whsec_dGVzdC1zZWNyZXQtdmFsdWUtMTIzNDU2Nzg5MA=="  # debe matchear el del API

# Endpoints esperados (28 totales — PR #20 borró 5 rutas: /profile/risk-profile,
# /user/risk_profile {GET,PUT} y /user/accounts_names {GET,PUT})
EXPECTED_ROUTES = {
    ("GET", "/"),
    ("GET", "/accounts"),
    ("POST", "/accounts"),
    ("GET", "/accounts/dividends/{account_id}"),
    ("GET", "/accounts/metrics/{account_id}"),
    ("GET", "/accounts/positions/{account_id}"),
    ("GET", "/accounts/transactions/{account_id}"),
    ("GET", "/accounts/{account_id}"),
    ("GET", "/assets"),
    ("POST", "/assets"),
    ("GET", "/assets/{asset_id}"),
    ("GET", "/assets/{asset_id}/prices"),
    ("POST", "/assets/{asset_id}/prices"),
    ("GET", "/dividends"),
    ("GET", "/health"),
    ("POST", "/pdf/extract_mutual_funds"),
    ("POST", "/pdf/extract_stocks_etf_1"),
    ("POST", "/pdf/extract_stocks_etf_2"),
    ("GET", "/positions"),
    ("GET", "/preferences"),
    ("PUT", "/preferences"),
    ("GET", "/profile"),
    ("PUT", "/profile"),
    ("GET", "/protected"),
    ("POST", "/risk_profile"),
    ("GET", "/transactions"),
    ("POST", "/transactions"),
    ("POST", "/webhooks/clerk"),
    ("GET", "/portfolio/dashboard"),
    ("POST", "/portfolio/rebuild"),
}


# ────────────────────────────────────────────────────────────────────────────
# Test infra
# ────────────────────────────────────────────────────────────────────────────
class Report:
    def __init__(self, label: str):
        self.label = label
        self.passed: list[str] = []
        self.failed: list[tuple[str, str]] = []

    def ok(self, name: str):
        self.passed.append(name)
        print(f"  ✅ {name}")

    def fail(self, name: str, reason: str):
        self.failed.append((name, reason))
        print(f"  ❌ {name} — {reason}")

    def summary(self) -> int:
        print()
        print("═" * 70)
        print(f"  RESULTADO ({self.label}): {len(self.passed)} OK, {len(self.failed)} FAIL")
        print("═" * 70)
        if self.failed:
            for name, reason in self.failed:
                print(f"  ❌ {name}: {reason}")
            return 1
        print("  🎉 TODAS LAS PRUEBAS PASARON")
        return 0


def section(title: str):
    print()
    print(f"━━━ {title} ━━━")


# ────────────────────────────────────────────────────────────────────────────
# Fase 2 — API contract (HTTP)
# ────────────────────────────────────────────────────────────────────────────
def test_routes_registered(r: Report, client: httpx.Client):
    section(f"Fase 2.1 — Rutas registradas ({len(EXPECTED_ROUTES)} esperadas)")
    try:
        spec = client.get("/openapi.json").json()
    except Exception as e:
        r.fail("openapi.json", str(e))
        return
    actual = {(m.upper(), p) for p, methods in spec["paths"].items() for m in methods}
    missing = EXPECTED_ROUTES - actual
    extra = actual - EXPECTED_ROUTES - {("OPTIONS", p) for p in actual}  # CORS preflight
    if missing:
        r.fail("rutas registradas", f"faltan: {missing}")
        return
    if extra:
        # Permitimos extras (no rompen)
        print(f"     (info: {len(extra)} rutas extra no esperadas: {extra})")
    r.ok(f"{len(EXPECTED_ROUTES)}/{len(EXPECTED_ROUTES)} rutas registradas exactamente como contrato")


def test_public_endpoints(r: Report, client: httpx.Client):
    section("Fase 2.2 — Endpoints públicos responden 200")
    for path in ["/", "/health"]:
        try:
            resp = client.get(path)
            if resp.status_code == 200:
                r.ok(f"GET {path} → 200")
            else:
                r.fail(f"GET {path}", f"got {resp.status_code}")
        except Exception as e:
            r.fail(f"GET {path}", str(e))


def test_protected_endpoints_reject_401(r: Report, client: httpx.Client):
    section("Fase 2.3 — Endpoints protegidos rechazan 401 sin token")
    protected = [
        ("GET", "/profile"),
        ("PUT", "/profile"),
        ("GET", "/accounts"),
        ("POST", "/accounts"),
        ("GET", "/accounts/00000000-0000-0000-0000-000000000000"),
        ("GET", "/accounts/metrics/00000000-0000-0000-0000-000000000000"),
        ("GET", "/accounts/positions/00000000-0000-0000-0000-000000000000"),
        ("GET", "/accounts/transactions/00000000-0000-0000-0000-000000000000"),
        ("GET", "/accounts/dividends/00000000-0000-0000-0000-000000000000"),
        ("GET", "/assets"),
        ("POST", "/assets"),
        ("GET", "/assets/00000000-0000-0000-0000-000000000000"),
        ("GET", "/assets/00000000-0000-0000-0000-000000000000/prices"),
        ("POST", "/assets/00000000-0000-0000-0000-000000000000/prices"),
        ("GET", "/dividends"),
        ("GET", "/transactions"),
        ("POST", "/transactions"),
        ("GET", "/positions"),
        ("GET", "/preferences"),
        ("PUT", "/preferences"),
        ("POST", "/risk_profile"),
        ("POST", "/pdf/extract_stocks_etf_1"),
        ("POST", "/pdf/extract_mutual_funds"),
        ("POST", "/pdf/extract_stocks_etf_2"),
        ("GET", "/protected"),
        ("GET", "/portfolio/dashboard"),
        ("POST", "/portfolio/rebuild"),
    ]
    ok = 0
    for method, path in protected:
        try:
            resp = client.request(method, path, json={})
            if resp.status_code == 401:
                ok += 1
            else:
                r.fail(f"{method} {path}", f"got {resp.status_code} esperaba 401")
        except Exception as e:
            r.fail(f"{method} {path}", str(e))
    if ok == len(protected):
        r.ok(f"{ok}/{len(protected)} endpoints protegidos rechazan 401")


# ────────────────────────────────────────────────────────────────────────────
# Fase 3 — Webhook svix
# ────────────────────────────────────────────────────────────────────────────
def _sign_webhook(payload: dict, msg_id: str) -> tuple[bytes, dict]:
    body = json.dumps(payload)
    now = datetime.now(timezone.utc)
    wh = Webhook(WEBHOOK_SECRET)
    sig = wh.sign(msg_id, now, body)
    return body.encode(), {
        "svix-id": msg_id,
        "svix-timestamp": str(int(now.timestamp())),
        "svix-signature": sig,
        "content-type": "application/json",
    }


def test_webhook_clerk(r: Report, client: httpx.Client):
    section("Fase 3 — Webhook Clerk (svix)")

    # 1. firma inválida → 400
    resp = client.post(
        "/webhooks/clerk",
        content=b"{}",
        headers={
            "svix-id": "x",
            "svix-timestamp": "1",
            "svix-signature": "v1,bad",
            "content-type": "application/json",
        },
    )
    if resp.status_code == 400:
        r.ok("firma svix inválida → 400")
    else:
        r.fail("firma svix inválida", f"got {resp.status_code}")

    # 2. headers faltantes → 400
    resp = client.post("/webhooks/clerk", content=b"{}")
    if resp.status_code == 400:
        r.ok("headers svix faltantes → 400")
    else:
        r.fail("headers svix faltantes", f"got {resp.status_code}")

    # 3. user.created con firma válida
    clerk_id = f"{TEST_USER_PREFIX}webhook_test"
    body, headers = _sign_webhook(
        {
            "type": "user.created",
            "data": {
                "id": clerk_id,
                "primary_email_address_id": "e1",
                "email_addresses": [{"id": "e1", "email_address": "webhook@test.io"}],
            },
        },
        "msg_wh_1",
    )
    resp = client.post("/webhooks/clerk", content=body, headers=headers)
    if resp.status_code == 200 and resp.json() == {"status": "ok"}:
        r.ok("user.created → 200 con shape {status:ok} 1:1 Eduardo")
    else:
        r.fail("user.created", f"got {resp.status_code} {resp.text}")

    # 4. user.deleted con firma válida
    body, headers = _sign_webhook(
        {"type": "user.deleted", "data": {"id": clerk_id}},
        "msg_wh_2",
    )
    resp = client.post("/webhooks/clerk", content=body, headers=headers)
    if resp.status_code == 200:
        r.ok("user.deleted → 200")
    else:
        r.fail("user.deleted", f"got {resp.status_code}")


# ────────────────────────────────────────────────────────────────────────────
# Fase 4 — Data layer (repos directos, no HTTP)
# ────────────────────────────────────────────────────────────────────────────
async def test_data_layer(r: Report):
    section("Fase 4.1 — Capa de datos: setup")
    u1_id = f"{TEST_USER_PREFIX}u1"
    u2_id = f"{TEST_USER_PREFIX}u2"

    async with SessionLocal() as db:
        u1 = await user_repo.get_or_create_by_clerk_id(db, u1_id, "inttest_u1@test.io")
        u2 = await user_repo.get_or_create_by_clerk_id(db, u2_id, "inttest_u2@test.io")
    if u1 and u2 and u1.clerk_id == u1_id and u2.clerk_id == u2_id:
        r.ok("user_repo.get_or_create_by_clerk_id (JIT create)")
    else:
        r.fail("user_repo create", "profiles no creadas")
        return

    section("Fase 4.2 — Asset catalog + price")
    async with SessionLocal() as db:
        symbol = f"_INTTEST{int(time.time())}"
        asset = await asset_repo.create(
            db,
            AssetCreate(symbol=symbol, name="Integration Test ETF",
                        kind=AssetKind.etf, currency="USD"),
        )
        await asset_price_repo.upsert(
            db,
            asset.id,
            AssetPriceCreate(date=date.today(), close=Decimal("100.00"),
                             currency="USD", source="integration_test"),
        )
    r.ok(f"asset {symbol} creado + price upserted")

    section("Fase 4.3 — Accounts (CRUD + isolation)")
    async with SessionLocal() as db:
        acc1 = await account_repo.create(db, u1_id, AccountCreate(name="acc1", currency="USD"))
        acc2 = await account_repo.create(db, u2_id, AccountCreate(name="acc2", currency="USD"))

    async with SessionLocal() as db:
        u1_accs = await account_repo.list_for_user(db, u1_id)
        u2_accs = await account_repo.list_for_user(db, u2_id)
        # isolation: u1 ve solo acc1, u2 solo acc2
        if (acc1.id in {a.id for a in u1_accs}
                and acc1.id not in {a.id for a in u2_accs}):
            r.ok("account isolation: u1 ve su account, u2 no")
        else:
            r.fail("account isolation", "FUGA detectada")

    section("Fase 4.4 — Transaction CRUD + isolation enforcement")
    async with SessionLocal() as db:
        from app.repositories import transaction_repo
        tx = await transaction_repo.create_for_user(
            db,
            u1_id,
            TransactionCreate(
                account_id=acc1.id,
                asset_id=asset.id,
                kind=TransactionKind.buy,
                quantity=Decimal("10"),
                price=Decimal("100"),
                fee=Decimal("0"),
                executed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        )
        if tx is not None:
            r.ok("transaction creada para u1 en su account")
        else:
            r.fail("transaction create", "retornó None inesperado")

        # u2 intenta postear tx en acc1 (no es de u2)
        bad = await transaction_repo.create_for_user(
            db,
            u2_id,
            TransactionCreate(
                account_id=acc1.id,
                asset_id=asset.id,
                kind=TransactionKind.buy,
                quantity=Decimal("999"),
                price=Decimal("1"),
                executed_at=datetime.now(tz=timezone.utc),
            ),
        )
        if bad is None:
            r.ok("isolation: u2 NO puede crear tx en account de u1 (None)")
        else:
            r.fail("transaction isolation", "u2 LOGRÓ crear tx en acc1 — FUGA")

    section("Fase 4.5 — Account detail (embeds + isolation)")
    async with SessionLocal() as db:
        # Agregar 1 dividend para tener data en el embed
        spy = asset
        from app.models.dividend import Dividend
        d = Dividend(
            account_id=acc1.id,
            asset_id=spy.id,
            date=date(2026, 1, 1),
            gross_amount=Decimal("50"),
            tax_amount=Decimal("5"),
            net_amount=Decimal("45"),
        )
        db.add(d)
        await db.commit()

    async with SessionLocal() as db:
        det_u1 = await account_repo.get_for_user_with_detail(db, u1_id, acc1.id)
        det_u2 = await account_repo.get_for_user_with_detail(db, u2_id, acc1.id)

        if (det_u1 is not None
                and len(det_u1.transactions) >= 1
                and len(det_u1.dividends) >= 1
                and isinstance(det_u1.positions, list)):
            r.ok("account detail: embeds transactions+dividends+positions OK para u1")
        else:
            r.fail("account detail u1",
                   f"transactions={len(det_u1.transactions) if det_u1 else 'None'}, "
                   f"dividends={len(det_u1.dividends) if det_u1 else 'None'}")

        if det_u2 is None:
            r.ok("account detail isolation: u2 → None pidiendo acc1")
        else:
            r.fail("account detail isolation u2",
                   f"u2 vio acc1 — FUGA")

    section("Fase 4.6 — Preferences upsert + isolation")
    async with SessionLocal() as db:
        pref1 = await user_preference_repo.upsert_for_user(
            db, u1_id,
            UserPreferenceUpdate(pnl_percentage_account_daily=Decimal("0.05")),
        )
        # actualizar otro campo, verificar que pnl no se pierde
        pref1b = await user_preference_repo.upsert_for_user(
            db, u1_id,
            UserPreferenceUpdate(asset_weight_weekly=Decimal("0.1")),
        )
        if (pref1b.pnl_percentage_account_daily == Decimal("0.05")
                and pref1b.asset_weight_weekly == Decimal("0.1")):
            r.ok("preferences upsert con merge (no override de campos no enviados)")
        else:
            r.fail("preferences merge",
                   f"pnl={pref1b.pnl_percentage_account_daily} weight={pref1b.asset_weight_weekly}")

        # u2 no debe ver preferences de u1
        pref_u2 = await user_preference_repo.get_for_user(db, u2_id)
        if pref_u2 is None:
            r.ok("preferences isolation: u2 → None")
        else:
            r.fail("preferences isolation", "u2 vio preferences de otro user")

    section("Fase 4.7 — Risk profile update")
    async with SessionLocal() as db:
        u1_obj = (await db.execute(
            select(Profile).where(Profile.clerk_id == u1_id)
        )).scalar_one()
        updated = await user_repo.update_risk_profile(db, u1_obj, RiskProfile.moderate)
        if updated.risk_profile == RiskProfile.moderate:
            r.ok("risk_profile persiste como enum 'moderate'")
        else:
            r.fail("risk_profile", f"got {updated.risk_profile}")

    section("Fase 4.8 — Assets list filters (1:1 Eduardo)")
    async with SessionLocal() as db:
        # filtro symbol exact
        exact = await asset_repo.list_all(db, symbol_exact=symbol)
        if any(a.symbol == symbol for a in exact):
            r.ok(f"GET /assets?symbol={symbol[:10]}... exact match")
        else:
            r.fail("assets symbol exact", "no encontró el asset")

        # filtro kind
        etfs = await asset_repo.list_all(db, kind=AssetKind.etf, limit=500)
        if all(a.kind == AssetKind.etf for a in etfs):
            r.ok(f"GET /assets?kind=etf devuelve solo ETFs ({len(etfs)} items)")
        else:
            r.fail("assets kind filter", "mixed kinds returned")

    section("Fase 4.9 — Asset detail prices DESC")
    async with SessionLocal() as db:
        # Agregar 3 precios con fechas distintas
        for d_, p in [(date(2026,1,1), 50), (date(2026,3,1), 60), (date(2026,2,1), 55)]:
            await asset_price_repo.upsert(
                db, asset.id,
                AssetPriceCreate(date=d_, close=Decimal(p), currency="USD", source="test"),
            )
    async with SessionLocal() as db:
        detail = await asset_repo.get_by_id_with_prices(db, asset.id)
        dates = [p.date for p in detail.prices]
        if dates == sorted(dates, reverse=True):
            r.ok(f"GET /assets/{{id}} prices DESC by date: {dates[:3]}...")
        else:
            r.fail("prices ordering", f"orden incorrecto: {dates[:5]}")

    section("Fase 4.10 — Rename account")
    async with SessionLocal() as db:
        renamed = await account_repo.rename(db, u1_id, acc1.id, "renombrada")
        # u2 NO puede renombrar la cuenta de u1
        not_owner = await account_repo.rename(db, u2_id, acc1.id, "hacked")
        if renamed and renamed.name == "renombrada" and not_owner is None:
            r.ok("account rename OK + isolation (u2 no puede renombrar acc1)")
        else:
            r.fail("rename",
                   f"renamed={renamed.name if renamed else 'None'} not_owner={not_owner}")


# ────────────────────────────────────────────────────────────────────────────
# Fase 5 — Ingestion (sintética, sin dependencias externas)
# ────────────────────────────────────────────────────────────────────────────
async def test_ingestion_pdf_stocks_etf_1(r: Report):
    section("Fase 5.1 — pdf_repo.stocks_etf_1 con filas sintéticas")
    from app.repositories import pdf_repo

    # Setup: usuario + asset + account
    u_id = f"{TEST_USER_PREFIX}pdf_user"
    async with SessionLocal() as db:
        u = await user_repo.get_or_create_by_clerk_id(db, u_id, "pdf@test.io")
        symbol = f"_INTTEST_PDF{int(time.time())}"
        asset = await asset_repo.create(
            db,
            AssetCreate(symbol=symbol, name="PDF Test Stock",
                        kind=AssetKind.stock, currency="USD"),
        )
        acc = await account_repo.create(db, u_id, AccountCreate(name="PDF Acc", currency="USD"))

    # Filas sintéticas en el formato exacto que produce processing_pdf.extract_stocks_etf_1
    # (purchase_sales + dividends_rows)
    purchase_sales = [
        # [fecha, nombre, simbolo, categoria, aporte, acciones_compradas, rescate, acciones_vendidas]
        ["2026-01-15", "PDF Test Stock", symbol, "stock", 1000.0, 10.0, 0.0, 0.0],
        ["2026-02-15", "PDF Test Stock", symbol, "stock", 0.0, 0.0, 500.0, 5.0],
    ]
    dividends_rows = [
        # [fecha, nombre, simbolo, categoria, monto_bruto, monto_impuestos, monto_neto]
        ["2026-03-15", "PDF Test Stock", symbol, "stock", 100.0, 15.0, 85.0],
    ]
    async with SessionLocal() as db:
        result = await pdf_repo.stocks_etf_1(
            db, u_id, [purchase_sales, dividends_rows], acc.id
        )

    if (result["compras_ventas_guardadas"] == 2
            and result["dividendos_guardados"] == 1
            and not result["errores_activos_faltantes"]):
        r.ok(f"PDF stocks_etf_1: 2 tx (buy+sell) + 1 dividend persistidos")
    else:
        r.fail("pdf stocks_etf_1", f"result={result}")

    # Verificar en DB
    async with SessionLocal() as db:
        det = await account_repo.get_for_user_with_detail(db, u_id, acc.id)
        if len(det.transactions) == 2 and len(det.dividends) == 1:
            kinds = sorted(t.kind.value for t in det.transactions)
            if kinds == ["buy", "sell"]:
                r.ok("PDF ingestion preserva kind buy/sell desde aporte/rescate")
            else:
                r.fail("PDF kinds", f"got {kinds}")
        else:
            r.fail("PDF persist",
                   f"tx={len(det.transactions)} div={len(det.dividends)}")


async def test_ingestion_pdf_mutual_funds(r: Report):
    section("Fase 5.2 — pdf_repo.save_mutual_funds (Fintual)")
    from app.repositories import pdf_repo

    u_id = f"{TEST_USER_PREFIX}fund_user"
    async with SessionLocal() as db:
        u = await user_repo.get_or_create_by_clerk_id(db, u_id, "fund@test.io")
        # Eduardo's mutual fund pattern: name + series (symbol)
        fund_name = "_INTTEST_FundName"
        fund_series = f"_INTTEST_S{int(time.time())}"
        asset = await asset_repo.create(
            db,
            AssetCreate(symbol=fund_series, name=fund_name,
                        kind=AssetKind.fund, currency="USD"),
        )
        acc = await account_repo.create(
            db, u_id, AccountCreate(name="Fintual Acc", broker="Fintual", currency="USD")
        )

    # Filas en el formato extract_mutual_funds:
    # [fecha, nombre_inversion, nombre_fondo, serie_fondo, aportes, rescate, aportes_cpl, rescate_cpl]
    rows = [
        ["15/01/2026", "Risky Norris", fund_name, fund_series, 100.0, 0.0, 1000.0, 0.0],
        ["20/02/2026", "Risky Norris", fund_name, fund_series, 0.0, 50.0, 0.0, 1100.0],
    ]
    async with SessionLocal() as db:
        result = await pdf_repo.save_mutual_funds(db, u_id, rows, acc.id)

    if result["compras_ventas_guardadas"] == 2 and not result["errores_activos_faltantes"]:
        r.ok("PDF mutual_funds: 2 tx (aporte + rescate) persistidas")
    else:
        r.fail("pdf mutual_funds", f"result={result}")


async def test_ingestion_twelvedata(r: Report):
    section("Fase 5.3 — TwelveData sync (1 símbolo)")
    api_key = os.environ.get("TWELVEDATA_API_KEY")
    if not api_key:
        print("     (skip: TWELVEDATA_API_KEY no seteada)")
        print("     Para activar este test:")
        print("        export TWELVEDATA_API_KEY='tu-api-key-de-twelvedata'")
        print("     Validará el roundtrip TwelveData -> Neon insertando precio para 1 símbolo.")
        return

    import requests
    try:
        resp = requests.get(
            "https://api.twelvedata.com/time_series",
            params={"symbol": "AAPL", "interval": "1day",
                    "outputsize": 1, "apikey": api_key},
            timeout=10,
        )
        data = resp.json()
        if "values" in data and data["values"]:
            r.ok(f"TwelveData responde: AAPL close={data['values'][0]['close']}")
        else:
            r.fail("TwelveData fetch", f"response: {data}")
    except Exception as e:
        r.fail("TwelveData fetch", str(e))


# ────────────────────────────────────────────────────────────────────────────
# Fase 6 — Portfolio reconstruction (time series → snapshots + positions)
# ────────────────────────────────────────────────────────────────────────────
async def test_portfolio_reconstruction(r: Report):
    """Test determinista de portfolio_repo: txs sintéticas → series → snapshots.

    Setup:
      D-10: buy 10 @ 100 (invested 1000)
      D-5:  buy  5 @ 120 (invested 1600; avg_cost = 1600/15 = 106.66...)
      D-2:  sell 3 @ 130 (realized 3*(130-106.66) = 70; qty=12, invested≈1280)

    Precios diarios D-10..D-1 con D-1=140; D=hoy sin precio → forward-fill 140.

    Expectativas:
      - len(snapshots) == 11  (D-10 .. D=today inclusive)
      - snapshots[-1].total_value ≈ 12 * 140 = 1680
      - snapshots[-1].unrealized_pnl ≈ 1680 - 1280 = 400
      - positions latest: qty=12, avg_cost≈106.66, realized_pnl≈70
    """
    from app.repositories import portfolio_repo
    from app.models.portfolio_snapshot import PortfolioSnapshot
    from app.models.position import Position

    section("Fase 6.1 — Reconstrucción de portafolio")

    u_id = f"{TEST_USER_PREFIX}portfolio_max"
    today = date.today()
    d10 = today - timedelta(days=10)
    d5 = today - timedelta(days=5)
    d2 = today - timedelta(days=2)

    async with SessionLocal() as db:
        await user_repo.get_or_create_by_clerk_id(db, u_id, "portfolio@inttest.io")
        acc = await account_repo.create(
            db, u_id, AccountCreate(name="_inttest_portfolio_acc", currency="USD")
        )

        ast = await asset_repo.create(
            db,
            AssetCreate(
                symbol=f"_INTTEST_PORTRECON_{int(time.time())}",
                name="_INTTEST_PORTRECON asset",
                kind=AssetKind.stock,
                currency="USD",
            ),
        )

        # Precios D-10..D-1 (10 días; sin precio para hoy → forward-fill desde D-1)
        # closes: 100, 104, 108, 112, 116, 120, 124, 128, 132, 136 (D-1)
        for i, days_ago in enumerate(range(10, 0, -1)):
            d = today - timedelta(days=days_ago)
            close = Decimal("100") + Decimal(i) * Decimal("4")
            await asset_price_repo.upsert(
                db,
                ast.id,
                AssetPriceCreate(
                    date=d, close=close, currency="USD", source="_inttest",
                ),
            )

        from app.repositories import transaction_repo
        await transaction_repo.create_for_user(
            db, u_id,
            TransactionCreate(
                account_id=acc.id, asset_id=ast.id,
                kind=TransactionKind.buy,
                quantity=Decimal("10"), price=Decimal("100"), fee=Decimal("0"),
                executed_at=datetime.combine(d10, datetime.min.time(), tzinfo=timezone.utc),
            ),
        )
        await transaction_repo.create_for_user(
            db, u_id,
            TransactionCreate(
                account_id=acc.id, asset_id=ast.id,
                kind=TransactionKind.buy,
                quantity=Decimal("5"), price=Decimal("120"), fee=Decimal("0"),
                executed_at=datetime.combine(d5, datetime.min.time(), tzinfo=timezone.utc),
            ),
        )
        await transaction_repo.create_for_user(
            db, u_id,
            TransactionCreate(
                account_id=acc.id, asset_id=ast.id,
                kind=TransactionKind.sell,
                quantity=Decimal("3"), price=Decimal("130"), fee=Decimal("0"),
                executed_at=datetime.combine(d2, datetime.min.time(), tzinfo=timezone.utc),
            ),
        )

    # Cómputo + persist
    async with SessionLocal() as db:
        snaps, pos = await portfolio_repo.compute_user_series(db, u_id)
        n_snaps = await portfolio_repo.replace_snapshots(db, u_id, snaps)
        n_pos = await portfolio_repo.replace_positions(db, u_id, pos)

    expected_days = 11  # D-10..D=today inclusive
    if n_snaps == expected_days:
        r.ok(f"snapshots: {n_snaps} días (D-10..today)")
    else:
        r.fail("snapshots count", f"got {n_snaps}, expected {expected_days}")

    if n_pos == 1:
        r.ok(f"positions persisted: {n_pos}")
    else:
        r.fail("positions count returned", f"got {n_pos}, expected 1")

    # Validar último snapshot
    async with SessionLocal() as db:
        q = await db.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.user_id == u_id)
            .order_by(PortfolioSnapshot.date.desc())
            .limit(1)
        )
        latest = q.scalar_one_or_none()

    if latest is None:
        r.fail("latest snapshot", "no se persistió ninguno")
    else:
        # 12 qty * 136 (precio D-1 forward-fill a hoy) = 1632
        expected_value = Decimal("1632")
        if abs((latest.total_value or Decimal("0")) - expected_value) < Decimal("0.01"):
            r.ok(f"snapshot.total_value = {latest.total_value} (esperado 1632)")
        else:
            r.fail("total_value", f"got {latest.total_value}, expected {expected_value}")

        # unrealized_pnl = 1632 - invested_actual. invested después de sell:
        # 1600 - avg_cost*3 = 1600 - (1600/15)*3 = 1600 - 320 = 1280
        # unrealized = 1632 - 1280 = 352
        expected_unrealized = Decimal("352")
        if abs((latest.unrealized_pnl or Decimal("0")) - expected_unrealized) < Decimal("0.01"):
            r.ok(f"snapshot.unrealized_pnl = {latest.unrealized_pnl} (esperado 352)")
        else:
            r.fail(
                "unrealized_pnl",
                f"got {latest.unrealized_pnl}, expected {expected_unrealized}",
            )

    # Validar positions latest
    async with SessionLocal() as db:
        pq = await db.execute(
            select(Position).where(Position.account_id == acc.id)
        )
        positions = pq.scalars().all()

    if len(positions) == 1:
        p = positions[0]
        # qty = 12, avg_cost = 1600/15 ≈ 106.6667
        if p.quantity == Decimal("12") and abs(p.avg_cost - Decimal("106.6666666666666667")) < Decimal("0.01"):
            r.ok(f"position latest: qty={p.quantity}, avg_cost={p.avg_cost:.4f}")
        else:
            r.fail("position state", f"qty={p.quantity}, avg_cost={p.avg_cost}")

        # realized_pnl ≈ 3*(130 - 106.66) = 70
        if abs((p.realized_pnl or Decimal("0")) - Decimal("70")) < Decimal("0.1"):
            r.ok(f"realized_pnl = {p.realized_pnl:.4f} (esperado 70)")
        else:
            r.fail("realized_pnl", f"got {p.realized_pnl}, expected 70")
    else:
        r.fail("positions count", f"expected 1, got {len(positions)}")

    # Validar shape del dashboard
    section("Fase 6.2 — Dashboard data (read)")
    async with SessionLocal() as db:
        dash = await portfolio_repo.get_dashboard_data(db, u_id)

    if "summary" in dash and "trend" in dash and "account_distribution" in dash and "positions" in dash:
        r.ok("dashboard shape: summary + trend + account_distribution + positions")
    else:
        r.fail("dashboard shape", f"keys: {list(dash.keys())}")

    # NOTA: user_repo.get_or_create_by_clerk_id auto-crea "Mi cuenta principal"
    # para users nuevos (JIT default account). Por eso linked_accounts=2
    # (la default + _inttest_portfolio_acc creada por este test). active_positions
    # es 1 porque solo agregamos tx a nuestra cuenta de test.
    if dash["summary"]["active_positions"] == 1 and dash["summary"]["linked_accounts"] == 2:
        r.ok("dashboard.summary contadores OK (positions=1 + default+test accounts=2)")
    else:
        r.fail(
            "dashboard.summary contadores",
            f"positions={dash['summary']['active_positions']}, accounts={dash['summary']['linked_accounts']}",
        )

    # Single-currency (USD): los escalares total_value/invested/unrealized
    # NO son None, y total_value_by_currency tiene 1 sola entrada (USD).
    summary = dash["summary"]
    if (summary["total_value"] is not None
            and list(summary["total_value_by_currency"].keys()) == ["USD"]
            and abs(summary["total_value_by_currency"]["USD"] - Decimal("1632")) < Decimal("0.01")):
        r.ok(f"single-currency USD: scalar={summary['total_value']} == by_currency['USD']={summary['total_value_by_currency']['USD']}")
    else:
        r.fail(
            "shape by currency",
            f"scalar={summary['total_value']}, by_currency={summary['total_value_by_currency']}",
        )

    if len(dash["trend"]) == expected_days:
        r.ok(f"dashboard.trend tiene {len(dash['trend'])} puntos")
    else:
        r.fail("dashboard.trend", f"got {len(dash['trend'])} puntos, esperaba {expected_days}")


# ────────────────────────────────────────────────────────────────────────────
# Fase 7 — End-to-End: PDF Fintual → ingest → rebuild → dashboard
# ────────────────────────────────────────────────────────────────────────────
async def test_e2e_pdf_to_dashboard(r: Report):
    """Flujo completo del producto:
      1. Pre-condición: existe asset en catálogo (por sync_stock_prices o manual)
      2. Usuario sube PDF → pdf_repo crea transactions + dividends
      3. Frontend dispara POST /portfolio/rebuild → snapshots persistidos
      4. Frontend lee GET /portfolio/dashboard → ve el portafolio actualizado

    Acá simulamos las 4 capas con repos directos (no podemos hacer HTTP
    autenticado en CI sin JWT real). El test verifica que el flujo de DATOS
    es consistente extremo a extremo.
    """
    from app.repositories import pdf_repo, portfolio_repo

    section("Fase 7.1 — E2E: PDF → ingest → rebuild → dashboard")

    u_id = f"{TEST_USER_PREFIX}e2e_pdf"

    async with SessionLocal() as db:
        await user_repo.get_or_create_by_clerk_id(db, u_id, "e2e@inttest.io")
        symbol = f"_INTTEST_E2E{int(time.time())}"
        asset = await asset_repo.create(
            db, AssetCreate(symbol=symbol, name=f"E2E Stock {symbol}",
                            kind=AssetKind.stock, currency="USD"),
        )
        acc = await account_repo.create(
            db, u_id, AccountCreate(name="_inttest_e2e_acc", currency="USD")
        )
        # Precio actual para que el dashboard tenga market_value
        await asset_price_repo.upsert(
            db, asset.id,
            AssetPriceCreate(date=date.today(), close=Decimal("150"),
                             currency="USD", source="_inttest"),
        )

    # ── 1. Simular subida de PDF ────────────────────────────────────────
    purchase_sales = [
        # buy 10@100 hace 5 días
        [(date.today() - timedelta(days=5)).strftime("%Y-%m-%d"),
         asset.name, symbol, "stock", 1000.0, 10.0, 0.0, 0.0],
    ]
    dividends_rows = [
        # dividendo 50 neto hace 2 días
        [(date.today() - timedelta(days=2)).strftime("%Y-%m-%d"),
         asset.name, symbol, "stock", 60.0, 10.0, 50.0],
    ]
    async with SessionLocal() as db:
        result = await pdf_repo.stocks_etf_1(
            db, u_id, [purchase_sales, dividends_rows], acc.id
        )

    if (result["compras_ventas_guardadas"] == 1
            and result["dividendos_guardados"] == 1
            and not result["errores_activos_faltantes"]):
        r.ok("paso 1 — PDF ingest: 1 tx (buy) + 1 dividend persistidos")
    else:
        r.fail("paso 1 — PDF ingest", f"result={result}")

    # ── 2. Disparar rebuild (lo que hace POST /portfolio/rebuild internamente) ──
    async with SessionLocal() as db:
        snaps, pos = await portfolio_repo.compute_user_series(db, u_id)
        n_snaps = await portfolio_repo.replace_snapshots(db, u_id, snaps)
        n_pos = await portfolio_repo.replace_positions(db, u_id, pos)

    # Esperamos ~6 días (D-5..today inclusive)
    if n_snaps == 6 and n_pos == 1:
        r.ok(f"paso 2 — rebuild: {n_snaps} snapshots + {n_pos} position")
    else:
        r.fail("paso 2 — rebuild", f"snaps={n_snaps}, pos={n_pos}, expected 6+1")

    # ── 3. Leer dashboard (lo que hace GET /portfolio/dashboard) ────────
    async with SessionLocal() as db:
        dash = await portfolio_repo.get_dashboard_data(db, u_id)

    summary = dash["summary"]
    # buy 10@100 → invested = 1000. Precio hoy = 150 → value = 10*150 = 1500.
    # unrealized = 1500 - 1000 = 500.
    expected_value = Decimal("1500")
    if (summary["total_value"] is not None
            and abs(summary["total_value"] - expected_value) < Decimal("0.01")):
        r.ok(f"paso 3 — dashboard.total_value = {summary['total_value']} (esperado 1500)")
    else:
        r.fail("paso 3 — dashboard.total_value",
               f"got {summary['total_value']}, expected {expected_value}")

    if summary["active_positions"] == 1:
        r.ok("paso 3 — dashboard.active_positions = 1")
    else:
        r.fail("paso 3 — active_positions",
               f"got {summary['active_positions']}, expected 1")

    # ── 4. Re-rebuild idempotente (mismo input → mismo output) ──────────
    async with SessionLocal() as db:
        snaps2, pos2 = await portfolio_repo.compute_user_series(db, u_id)
        n_snaps2 = await portfolio_repo.replace_snapshots(db, u_id, snaps2)
        n_pos2 = await portfolio_repo.replace_positions(db, u_id, pos2)

    if n_snaps2 == n_snaps and n_pos2 == n_pos:
        r.ok(f"paso 4 — rebuild idempotente: {n_snaps2} snapshots, {n_pos2} position")
    else:
        r.fail("paso 4 — rebuild idempotente",
               f"first={n_snaps}+{n_pos}, second={n_snaps2}+{n_pos2}")


# ────────────────────────────────────────────────────────────────────────────
# Cleanup
# ────────────────────────────────────────────────────────────────────────────
async def cleanup_test_data():
    """Borra todo lo creado con TEST_USER_PREFIX.

    Las FKs hacia profiles no tienen CASCADE explícito → hay que borrar en
    orden inverso de dependencias:
      1) accounts del user (cascade borra tx/div/pos)
      2) user_preferences del user
      3) portfolio_snapshots del user
      4) profiles
      5) asset_prices de los test assets
      6) assets de test
    """
    from app.models.portfolio_snapshot import PortfolioSnapshot
    from app.models.asset_price import AssetPrice

    async with SessionLocal() as db:
        # 1. Accounts (cascade)
        await db.execute(
            delete(Account).where(Account.user_id.like(f"{TEST_USER_PREFIX}%"))
        )
        # 2. UserPreferences
        await db.execute(
            delete(UserPreference).where(
                UserPreference.user_id.like(f"{TEST_USER_PREFIX}%")
            )
        )
        # 3. PortfolioSnapshots
        await db.execute(
            delete(PortfolioSnapshot).where(
                PortfolioSnapshot.user_id.like(f"{TEST_USER_PREFIX}%")
            )
        )
        # 4. Profiles
        await db.execute(
            delete(Profile).where(Profile.clerk_id.like(f"{TEST_USER_PREFIX}%"))
        )
        # 5. AssetPrices de assets de test (cascade by asset)
        result = await db.execute(
            select(Asset.id).where(Asset.symbol.like("_INTTEST%"))
        )
        asset_ids = [row[0] for row in result.all()]
        if asset_ids:
            await db.execute(
                delete(AssetPrice).where(AssetPrice.asset_id.in_(asset_ids))
            )
        # 6. Assets test
        await db.execute(
            delete(Asset).where(Asset.symbol.like("_INTTEST%"))
        )
        await db.commit()


# ────────────────────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────────────────────
async def main(api_url: str, label: str, cleanup: bool) -> int:
    print(f"╔══════════════════════════════════════════════════════════════════╗")
    print(f"║  INTEGRATION TEST — target: {label:<37}║")
    print(f"║  API: {api_url:<60}║")
    print(f"║  DB:  {os.getenv('DATABASE_URL', os.getenv('DATABASE_URL_DEV', '?'))[:60]:<60}║")
    print(f"╚══════════════════════════════════════════════════════════════════╝")

    r = Report(label)

    with httpx.Client(base_url=api_url, timeout=10.0) as client:
        # Fase 2: HTTP layer
        test_routes_registered(r, client)
        test_public_endpoints(r, client)
        test_protected_endpoints_reject_401(r, client)
        test_webhook_clerk(r, client)

    # Fase 4: data layer (repos directos)
    await test_data_layer(r)

    # Fase 5: ingestion
    await test_ingestion_pdf_stocks_etf_1(r)
    await test_ingestion_pdf_mutual_funds(r)
    await test_ingestion_twelvedata(r)

    # Fase 6: portfolio reconstruction
    await test_portfolio_reconstruction(r)

    # Fase 7: end-to-end (PDF → ingest → rebuild → dashboard)
    await test_e2e_pdf_to_dashboard(r)

    if cleanup:
        section("Cleanup: borrar profiles + assets de test")
        try:
            await cleanup_test_data()
            r.ok("test data borrada")
        except Exception as e:
            r.fail("cleanup", str(e))

    return r.summary()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--label", default="local")
    parser.add_argument("--no-cleanup", action="store_true")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.api_url, args.label, not args.no_cleanup)))
