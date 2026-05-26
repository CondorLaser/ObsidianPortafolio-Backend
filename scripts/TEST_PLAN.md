# Plan de pruebas — Backend Orion

## Resumen

| Fase | Cobertura | Modo | Estado |
|---|---|---|---|
| 1. Capa de datos | Migración + smoke test | Automático | ✅ |
| 2. API contract | Rutas, auth wiring, shapes | Automático | ✅ |
| 3. Webhook svix | Firma válida/inválida, user.* | Automático | ✅ |
| 4. Data layer | CRUD + isolation entre users | Automático | ✅ |
| 5. Ingestion | PDF Fintual + TwelveData | Auto (PDF) / requiere API key (TwelveData) | ✅ |
| 6. Frontend E2E | Browser → Zuplo → backend | **Manual** | Guiado abajo |

## Fases 1-5 — Automatizadas

### Cómo correrlas

```bash
# Contra Docker local (DB local):
./scripts/test_local.sh

# Contra Neon develop (DB cloud):
NEON_URL='postgresql+asyncpg://neondb_owner:<PASS>@ep-patient-truth-anbf88il-pooler.c-6.us-east-1.aws.neon.tech/neondb' \
  ./scripts/test_neon.sh

# Activar el sub-test de TwelveData (opcional, requiere API key):
export TWELVEDATA_API_KEY='tu-key'
./scripts/test_local.sh  # ahora incluye fetch real a TwelveData
```

### Resultado esperado

```
RESULTADO (local|neon): 26 OK, 0 FAIL
🎉 TODAS LAS PRUEBAS PASARON
```

### Qué cubre cada fase

**Fase 2** — `integration_test.py:test_routes_registered`, `test_public_endpoints`, `test_protected_endpoints_reject_401`
- 33 rutas exactas
- `GET /` y `GET /health` → 200
- 30 endpoints autenticados → 401 sin token

**Fase 3** — `integration_test.py:test_webhook_clerk`
- Firma svix inválida → 400
- Headers faltantes → 400
- `user.created` + `user.deleted` con firma válida → 200

**Fase 4** — `integration_test.py:test_data_layer`
- JIT user creation
- Asset catalog + price
- Account CRUD + isolation
- Transaction CRUD + isolation (u2 NO puede postear en account de u1)
- Account detail con embeds (transactions, dividends, positions)
- Preferences upsert con merge (no override de campos no enviados)
- Risk profile persiste como enum
- Assets filter exact (`?symbol=X`) y por kind
- Asset detail con prices ORDER BY date DESC
- Account rename con ownership check

**Fase 5** — `integration_test.py:test_ingestion_*` + scripts dedicados
- `pdf_repo.stocks_etf_1`: filas sintéticas → INSERT en transactions+dividends, kind buy/sell correcto
- `pdf_repo.save_mutual_funds`: filas sintéticas Fintual → INSERT en transactions
- `sync_stock_prices.fetch_prices` contra TwelveData (1 símbolo, opcional con API key)
- **`scripts/test_real_fintual_data.py`** — usa rows REALES extraídas manualmente de los certificados del usuario (82 tx). Bypassea pdfplumber pero valida toda la cadena de persistencia con data real.
- **`scripts/test_pdf_e2e.py`** — **END-TO-END**: PDF binario → pdfplumber → processing_pdf.extract_* → pdf_repo → DB. Requiere PDFs en `docs/pdfs/` (gitignored, data personal). Resultado real verificado: 36 compraventas + 71 dividendos del cert_stocks + 69 movimientos del cert_funds = **176 tx persistidas sin errores**.

### Tests E2E PDF — guía rápida

PDFs personales NO se commitean (data financiera). Guardar manualmente en:
```
ObsidianPortafolio-Backend/docs/pdfs/certificado.pdf                    # stocks/ETFs + dividendos
ObsidianPortafolio-Backend/docs/pdfs/certificado_de_transacciones.pdf   # fondos mutuos
```

Correr:
```bash
docker compose up -d        # Postgres local con schema migrado
DATABASE_URL_DEV='postgresql+asyncpg://orion:orion@localhost:5433/orion_dev' \
  ./venv/bin/python -m scripts.test_pdf_e2e
```

⚠️ Se corre con **venv local** (no `docker compose exec`) porque `docs/` no está montado al contenedor por seguridad. El test se conecta a la DB del Docker vía `localhost:5433`.

### Limpieza automática

Todo dato de test se crea con prefijo `_inttest_` (clerk_id) o `_INTTEST` (asset symbol). El script borra todo al final. Verificado que **Neon no queda con residuos**.

---

## Fase 6 — Frontend + Zuplo E2E (MANUAL)

Esta fase no se automatiza porque necesita un browser real con sesión Clerk activa.

### Pre-requisitos

1. Backend corriendo (apuntando a la DB que querés probar — local o Neon).
2. Frontend Next.js corriendo localmente.
3. Zuplo gateway configurado (revisar que el URL en `NEXT_PUBLIC_URL_GATEWAY` apunte al backend).
4. Cuenta Clerk dev (worthy-jackal-80) — podés crear test users en su dashboard.

### Setup paso a paso

**Backend contra Neon develop**:

```bash
cd ObsidianPortafolio-Backend
docker compose down
APP_ENV=prod \
DATABASE_URL='postgresql+asyncpg://neondb_owner:<PASS>@ep-patient-truth-anbf88il-pooler.c-6.us-east-1.aws.neon.tech/neondb' \
CLERK_ISSUER='https://worthy-jackal-80.clerk.accounts.dev' \
CLERK_WEBHOOK_SECRET='<el de Clerk Dashboard>' \
ALLOWED_ORIGINS='http://localhost:3000,https://condor-laser-main-57c2c96.d2.zuplo.dev' \
./venv/bin/uvicorn app.main:app --reload
```

**Frontend**:

```bash
cd ObsidianPortafolio-Frontend
# .env.local con keys reales:
#   NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
#   CLERK_SECRET_KEY=sk_test_...
#   NEXT_PUBLIC_URL_GATEWAY=http://localhost:8000  # bypass Zuplo para test directo
#   o NEXT_PUBLIC_URL_GATEWAY=https://condor-laser-main-57c2c96.d2.zuplo.dev/  # via Zuplo
npm install
npm run dev
```

Abrir <http://localhost:3000>.

### Checklist manual de prueba

Mientras navegás, abrí **DevTools → Network tab** para inspeccionar las requests.

1. **Login**
   - [ ] Sign-up con un email nuevo → recibís verificación
   - [ ] Sign-in con el email creado
   - [ ] DevTools muestra request a Clerk OK (sin errors)
   - [ ] Network: backend recibe webhook `user.created` (chequear log de uvicorn)
   - [ ] Backend crea profile en DB (verificar en psql/Neon SQL Editor: `SELECT * FROM profiles WHERE clerk_id = '...'`)

2. **Vista Cuentas (`/cuentas`)**
   - [ ] Hace request a `GET /accounts` con `Authorization: Bearer <JWT>`
   - [ ] Recibe `[]` (primera vez) o array de cuentas
   - [ ] Sin errores 401/500

3. **Crear cuenta** (si hay UI para esto)
   - [ ] POST `/accounts` con body `{name, broker, currency}`
   - [ ] 201 Created
   - [ ] La cuenta aparece en `/cuentas`

4. **Vista Cuenta Específica (`/cuentas/{id}`)**
   - [ ] GET `/accounts/{id}` retorna objeto con `transactions`, `dividends`, `positions`
   - [ ] (Inicialmente todos `[]`)

5. **Vista Activos (`/activos`)**
   - [ ] GET `/assets?kind=stock` (o similar)
   - [ ] Si Neon tiene 1888 assets, deberías ver una lista substancial

6. **Vista Activo Específico (`/activos/{id}`)**
   - [ ] GET `/assets/{asset_id}` retorna metadata + array de `prices` ordenados DESC
   - [ ] El primer price de `prices[0]` es el más reciente

7. **Vista Perfil (`/perfil`)**
   - [ ] GET `/profile` retorna `{clerk_id, email, created_at, risk_profile}`
   - [ ] Editar risk_profile → PATCH `/profile/risk-profile` o PUT `/profile` con body `{risk_profile: "moderate"}`
   - [ ] 200 OK + recargar muestra el cambio

8. **Onboarding (si aplica)**
   - [ ] POST `/risk_profile` con `{risk_profile: "conservative"}`
   - [ ] Setea risk_profile inicial

9. **PDFs Fintual** (si hay UI de upload)
   - [ ] Multipart POST a `/pdf/extract_stocks_etf_1` con un PDF real
   - [ ] Response: `{compras_ventas_guardadas: N, dividendos_guardados: M, errores_activos_faltantes: [...]}`
   - [ ] Verificar en DB: transactions + dividends del PDF aparecen

10. **CORS / Zuplo routing**
    - [ ] Sin errores CORS en console
    - [ ] Si Zuplo está en el medio: headers `Authorization` se preservan
    - [ ] Si Zuplo añade headers extras: backend los ignora (no fallan)

### Troubleshooting común

| Síntoma | Causa probable | Fix |
|---|---|---|
| 401 en TODAS las requests | `CLERK_ISSUER` mal seteado en backend | Confirmar `https://worthy-jackal-80.clerk.accounts.dev` |
| CORS error en browser | `ALLOWED_ORIGINS` no incluye el origen del frontend | Agregar `http://localhost:3000` o el dominio de Zuplo |
| 404 en `/profile/dividends` o `/profile/transactions` | Frontend usa rutas viejas (Eduardo las borró en su versión final) | Usar `/dividends` y `/transactions` standalone, o embebidos en `/accounts/{id}` |
| Webhook `user.created` no llega a backend | URL de webhook en Clerk Dashboard mal seteada / Neon no tiene túnel | Configurar webhook a `https://<backend-publica>/webhooks/clerk` con su secret |
| Backend crashea en startup | Falta `CLERK_WEBHOOK_SECRET` en env | Setear desde Clerk Dashboard → Webhooks → Signing Secret |

### Datos pre-cargados en Neon develop

Si testeás contra Neon develop, ya hay data real:

```
profiles:        14 (incluye eduardo, florencia, etc.)
accounts:         3
assets:        1888 (subió de 505 por GH Action de sync_stock_prices)
asset_prices: 217266 (sigue creciendo cada día con TwelveData)
transactions:    20
dividends:       14
```

Si querés usar uno de esos profiles como test user, podés:
1. Sign-in con el mismo email en Clerk
2. JIT user creation NO va a crearlo de nuevo (clerk_id ya existe)
3. Vas a ver toda la data asociada a ese profile

---

## Cómo correr el sync TwelveData manualmente

Si querés probar el cron de precios localmente (sin esperar al GH Action):

```bash
cd ObsidianPortafolio-Backend
export DATABASE_URL='postgresql://neondb_owner:<PASS>@ep-patient-truth-anbf88il-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require'
export TWELVEDATA_API_KEY='<tu-key>'
./venv/bin/python sync_stock_prices.py
```

Va a iterar cada asset con `kind='stock'` y agregar precios incrementalmente. Output esperado por símbolo:
```
[1/123] AAPL
 5 registros guardados
```

⚠️ Free tier de TwelveData = 8 requests/min → tarda ~1 segundo por símbolo + 8s sleep. Para 1888 assets potencialmente serían horas. Para test manual con 1-2 símbolos, editar el query del script.
