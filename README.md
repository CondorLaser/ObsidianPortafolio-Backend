# ObsidianPortafolio-Backend

API en FastAPI para Orion Portafolio. Auth vía Clerk (JWT), persistencia en Postgres con SQLAlchemy 2.0 async + Alembic, deploy productivo en Render apuntando a Neon.

**Estado actual**: 33 endpoints, schema 1:1 con Neon develop, contrato matcheado con el frontend mock (ver [docs/API_CONTRACT.md](docs/API_CONTRACT.md)).

---

## Quick start

### Con Docker Compose (recomendado)

```bash
cp .env.example .env.local        # editar con tus valores Clerk (gitignored)
docker compose up --build
```

Levanta dos containers:
- `orion-postgres` (Postgres 16 con volumen `orion_pgdata`, puerto host `5433`)
- `orion-api` (FastAPI con hot-reload + `alembic upgrade head` automático antes de uvicorn)

Swagger UI: <http://localhost:8000/docs>  
OpenAPI raw: <http://localhost:8000/openapi.json>

### Sin Docker (nativo)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env.local
# Levantar Postgres aparte (docker o brew install postgresql@16)
alembic upgrade head
uvicorn app.main:app --reload
```

---

## Variables de entorno

| Variable | Ejemplo | Cuándo |
|---|---|---|
| `APP_ENV` | `dev` \| `prod` | `dev` (default) usa `DATABASE_URL_DEV`; `prod` exige `DATABASE_URL`. |
| `DATABASE_URL_DEV` | `postgresql+asyncpg://orion:orion@localhost:5433/orion_dev` | DB local. |
| `DATABASE_URL` | `postgresql+asyncpg://neondb_owner:...@ep-...pooler.aws.neon.tech/neondb` | Override directo (Render/Neon prod). |
| `CLERK_ISSUER` | `https://worthy-jackal-80.clerk.accounts.dev` | Para verificar JWTs Clerk. |
| `CLERK_WEBHOOK_SECRET` | `whsec_...` | Para `POST /webhooks/clerk` (sin esto el endpoint devuelve 500). |
| `ALLOWED_ORIGINS` | `http://localhost:3000,https://...` | CORS, separados por coma. |
| `TWELVEDATA_API_KEY` | `xxxx` | Para `sync_stock_prices.py` (GH Action cron diario). |

⚠️ `config.py` normaliza `postgres://` → `postgresql+asyncpg://`. Para Neon: **no incluyas** `?sslmode=require` ni `?channel_binding=...` en la URL — asyncpg no los entiende; `db.py` activa SSL automáticamente vía `certifi` cuando detecta `*.neon.tech`.

---

## Arquitectura

```
app/
├── core/         # config (settings), db (engine, SessionLocal), auth (Clerk JWKS)
├── models/       # SQLAlchemy 2.0 ORM (15 modelos)
├── schemas/      # Pydantic v2 (Create/Read/Update por entidad)
├── repositories/ # acceso a datos, aplica isolation por user_id
├── routers/      # endpoints HTTP (13 routers, 33 endpoints)
└── main.py       # FastAPI app + CORS + include_router

alembic/          # migraciones
scripts/          # smoke_test, integration_test, sync_stock_prices, generate_api_contract
docs/             # API_CONTRACT.md (autogenerado), data-model
```

**Aislamiento por usuario** se enforza en la capa de **repositories**, no en los routers (validado con tests de isolation u1/u2).

**Decisión de PK**: `profiles.clerk_id` es la PK directa (varchar), no hay UUID interno. Toda FK user-scoped es `varchar` a `profiles.clerk_id`. Esto matchea el schema diseñado por Eduardo en Neon develop.

---

## Endpoints

Lista completa con shapes en [docs/API_CONTRACT.md](docs/API_CONTRACT.md) (autogenerado desde OpenAPI vivo).

Para regenerar el contrato:
```bash
docker compose up -d
./venv/bin/python -m scripts.generate_api_contract
```

### Resumen por área

| Área | Endpoints |
|---|---|
| **Públicos** (sin auth) | `GET /`, `GET /health` |
| **Webhook svix** | `POST /webhooks/clerk` (handle user.created/updated/deleted) |
| **Profile** | `GET/PUT /profile`, `PATCH /profile/risk-profile`, `POST /risk_profile` (onboarding) |
| **User (alias frontend)** | `GET/PUT /user/risk_profile`, `GET/PUT /user/accounts_names` |
| **Preferences** | `GET/PUT /preferences` (umbrales de alertas) |
| **Accounts** | `GET/POST /accounts`, `GET /accounts/{id}` (con embeds), `GET /accounts/{metrics\|positions\|transactions\|dividends}/{id}` |
| **Assets** | `GET/POST /assets`, `GET /assets/{id}` (con prices embebidos), `GET/POST /assets/{id}/prices` |
| **Transactions / Dividends / Positions** | `GET/POST /transactions`, `GET /dividends`, `GET /positions` (derivadas) |
| **Ingesta PDF Fintual** | `POST /pdf/extract_stocks_etf_1`, `POST /pdf/extract_mutual_funds`, `POST /pdf/extract_stocks_etf_2` |

---

## Migraciones (Alembic)

```bash
# Aplicar todas (default APP_ENV=dev contra Docker local):
alembic upgrade head

# Apuntar a Neon sin tocar .env.local:
APP_ENV=prod DATABASE_URL='postgresql+asyncpg://...neon.tech/neondb' \
  alembic upgrade head

# Crear nueva migración tras editar modelos:
alembic revision --autogenerate -m "describe change"

# Rollback al revisión anterior:
alembic downgrade -1
```

---

## Testing

### Suite integral automatizada

Cubre Fases 1-5 (data layer + API contract + webhook svix + isolation + ingestion). Detalle en [scripts/TEST_PLAN.md](scripts/TEST_PLAN.md).

```bash
# Contra Docker local:
./scripts/test_local.sh

# Contra Neon develop:
NEON_URL='postgresql+asyncpg://neondb_owner:...@...neon.tech/neondb' \
  ./scripts/test_neon.sh

# Con sub-test TwelveData (opcional con API key):
export TWELVEDATA_API_KEY='...'
./scripts/test_local.sh
```

Resultado esperado:
```
RESULTADO (local|neon): 27 OK, 0 FAIL
🎉 TODAS LAS PRUEBAS PASARON
```

### Tests específicos

```bash
docker compose exec api python -m scripts.smoke_test         # data layer baseline
docker compose exec api python -m scripts.test_real_fintual_data   # ingesta con data REAL Fintual
./venv/bin/python -m scripts.test_pdf_e2e   # E2E pdfplumber con PDFs en disco
```

### Fase 6 — Frontend E2E (manual)

Documentada en [scripts/TEST_PLAN.md](scripts/TEST_PLAN.md) con checklist DevTools paso a paso.

---

## Producción (Render + Neon)

Variables en Render → Environment del Web Service:

```
APP_ENV=prod
DATABASE_URL=postgresql+asyncpg://neondb_owner:...@ep-...pooler.aws.neon.tech/neondb
CLERK_ISSUER=https://worthy-jackal-80.clerk.accounts.dev
CLERK_WEBHOOK_SECRET=whsec_...
ALLOWED_ORIGINS=https://<dominio-frontend>
```

- **Pre-Deploy Command**: `alembic upgrade head`
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Sincronización de precios (cron)

`.github/workflows/sync_stock_prices.yml` corre diario 05:00 UTC contra TwelveData, inserta nuevos `asset_prices` en Neon. Secrets requeridos en GitHub:
- `DATABASE_URL` (Neon, formato `postgresql://...` sin asyncpg)
- `TWELVEDATA_API_KEY`

Manual:
```bash
DATABASE_URL='postgresql://neondb_owner:...?sslmode=require' \
TWELVEDATA_API_KEY='...' \
./venv/bin/python sync_stock_prices.py
```

---

## Modelos / Data model

15 tablas (matchean Neon develop 1:1):

```
profiles                          # clerk_id es PK varchar
├── accounts (user_id varchar)
│   ├── transactions (asset_id uuid)
│   ├── dividends   (asset_id uuid)
│   ├── positions   (asset_id uuid) ← materializadas, cómputo pendiente
│   ├── account_daily_metrics, account_monthly_metrics ← cómputo pendiente
│   └── ...
├── portfolio_snapshots
│   ├── portfolio_daily_metrics
│   └── portfolio_monthly_metrics
└── user_preferences

assets (catálogo global)
├── asset_prices
├── asset_daily_metrics, asset_monthly_metrics ← cómputo pendiente
```

Enums:
- `asset_kind`: `stock, etf, fund, crypto, other`
- `transaction_kind`: `buy, sell, dividend, fee, deposit, withdrawal`
- `risk_profile_kind`: `moderate, agressive, conservative` *(typo "agressive" preservado de Neon original)*

Ver schema completo en [docs/data-model.dbml](docs/data-model.dbml).

---

## Para el equipo frontend

1. **Contrato vivo**: [docs/API_CONTRACT.md](docs/API_CONTRACT.md) — autogenerado, siempre al día.
2. **Auth**: requests autenticadas llevan `Authorization: Bearer <Clerk JWT>`. El backend hace JIT user creation (crea `profile` automáticamente al primer hit autenticado si Clerk webhook todavía no llegó).
3. **Errores comunes**:
   - `401`: token Clerk faltante/inválido/expirado.
   - `404`: recurso no existe O no es del usuario (isolation).
   - `409`: conflict (ej. symbol asset duplicado).
   - `422`: validación Pydantic — revisar shape del body en el contrato.
4. **CORS**: el origen del frontend tiene que estar en `ALLOWED_ORIGINS`.
