# ObsidianPortafolio-Backend

API en FastAPI para Orion Portafolio. Auth vía Clerk (JWT), persistencia en Postgres con SQLAlchemy 2.0 async + Alembic.

## Preparación del entorno

```bash
python -m venv venv
source venv/bin/activate          # Windows: .\venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env.local        # edita .env.local con tus valores (no entra al repo)
```

## Variables de entorno

| Variable | Ejemplo | Uso |
|---|---|---|
| `APP_ENV` | `dev` o `prod` | Selector de ambiente. `dev` (default) usa `DATABASE_URL_DEV`. `prod` exige `DATABASE_URL` explícita. |
| `DATABASE_URL_DEV` | `postgresql+asyncpg://orion:orion@localhost:5433/orion_dev` | DB para dev local (Docker). Solo se usa cuando `APP_ENV=dev` y no hay `DATABASE_URL`. |
| `DATABASE_URL` | `postgresql+asyncpg://...neon.tech/neondb` | Override directo. Si está seteada, gana sobre `APP_ENV`. Render/Neon la inyectan en producción. |
| `CLERK_ISSUER` | `https://your-tenant.clerk.accounts.dev` | Issuer del JWT Clerk para verificar tokens. |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | Orígenes CORS separados por coma. |

`config.py` normaliza automáticamente `postgres://` → `postgresql+asyncpg://`. Si la URL apunta a `*.neon.tech`, `db.py` activa SSL con el bundle de `certifi`. **No incluyas `?sslmode=require` ni `?channel_binding=...`** — asyncpg no los entiende.

## Postgres local con Docker (dev)

```bash
docker run -d --name orion-postgres \
  -e POSTGRES_USER=orion -e POSTGRES_PASSWORD=orion -e POSTGRES_DB=orion_dev \
  -p 5433:5432 postgres:16-alpine
```

## Migraciones (Alembic)

```bash
# dev local (Docker, default APP_ENV=dev)
alembic upgrade head

# apuntar a Neon desde tu máquina sin tocar .env.local
APP_ENV=prod DATABASE_URL=postgresql+asyncpg://...neon.tech/neondb alembic upgrade head

# crear nueva migración tras editar modelos
alembic revision --autogenerate -m "describe change"
```

## Ejecución del servidor

```bash
# dev (Docker)
uvicorn app.main:app --reload

# apuntar a Neon en una sola corrida
APP_ENV=prod DATABASE_URL=postgresql+asyncpg://...neon.tech/neondb uvicorn app.main:app --reload
```

OpenAPI: http://localhost:8000/docs

## Producción (Render + Neon)

En Render → Environment Variables del Web Service:
- `APP_ENV=prod`
- `DATABASE_URL=postgresql+asyncpg://...neon.tech/neondb` (URL pooled, sin query params SSL)
- `CLERK_ISSUER=...`
- `ALLOWED_ORIGINS=https://<dominio-frontend>`

Pre-Deploy Command sugerido: `alembic upgrade head`. Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

## Endpoints

Públicos:
- `GET /` — health-ish.
- `GET /protected` — requiere JWT Clerk, devuelve `sub`.

Autenticados con `Bearer <Clerk JWT>`, prefijo `/api/v1`:

| Método | Path | Descripción |
|---|---|---|
| `GET`  | `/accounts` | Cuentas del usuario |
| `POST` | `/accounts` | Crear cuenta |
| `GET`  | `/assets` | Catálogo de instrumentos (filtro `?symbol=`) |
| `POST` | `/assets` | Alta de instrumento |
| `GET`  | `/assets/{symbol}/prices` | Serie histórica (`?from=YYYY-MM-DD&to=...`) |
| `POST` | `/assets/{symbol}/prices` | Upsert de precio diario |
| `GET`  | `/transactions` | Transacciones del usuario |
| `POST` | `/transactions` | Crear transacción |
| `GET`  | `/positions` | Posiciones derivadas (cantidad neta + costo promedio + último precio) |

## Estructura

```
app/
├── core/         # config, db engine, auth (Clerk JWKS + get_current_user)
├── models/       # SQLAlchemy ORM models
├── schemas/      # Pydantic v2 (Create / Read)
├── repositories/ # acceso a datos por entidad (filtra por user_id)
├── routers/      # endpoints HTTP
└── main.py       # app + CORS + include_router
alembic/          # migraciones
```

El aislamiento por usuario se enforza en los **repositories**, no en los routers.
