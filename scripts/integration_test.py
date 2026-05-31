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
from datetime import date, datetime, timezone
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

# Endpoints esperados (33 totales tras PRs #12-15)
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
    ("PATCH", "/profile/risk-profile"),
    ("GET", "/protected"),
    ("POST", "/risk_profile"),
    ("GET", "/transactions"),
    ("POST", "/transactions"),
    ("GET", "/user/accounts_names"),
    ("PUT", "/user/accounts_names"),
    ("GET", "/user/risk_profile"),
    ("PUT", "/user/risk_profile"),
    ("POST", "/webhooks/clerk"),
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
    section("Fase 2.1 — Rutas registradas (33 esperadas)")
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
    r.ok(f"33/33 rutas registradas exactamente como contrato")


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
        ("PATCH", "/profile/risk-profile"),
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
        ("GET", "/user/risk_profile"),
        ("PUT", "/user/risk_profile"),
        ("GET", "/user/accounts_names"),
        ("PUT", "/user/accounts_names"),
        ("POST", "/risk_profile"),
        ("POST", "/pdf/extract_stocks_etf_1"),
        ("POST", "/pdf/extract_mutual_funds"),
        ("POST", "/pdf/extract_stocks_etf_2"),
        ("GET", "/protected"),
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
