#!/usr/bin/env bash
# Suite contra Neon develop. Asume el venv local y la URL en env.
#
# Uso:
#   NEON_URL='postgresql+asyncpg://neondb_owner:...@...neon.tech/neondb' \
#     ./scripts/test_neon.sh
#
set -e
cd "$(dirname "$0")/.."

: "${NEON_URL:?NEON_URL no seteada — exportala antes de correr}"

# Parar docker compose si está arriba (para liberar puerto 8000)
docker compose down >/dev/null 2>&1 || true

# Matar uvicorn previo si existe
pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 1

echo "═══ Levantando uvicorn local apuntando a Neon develop ═══"
APP_ENV=prod \
DATABASE_URL="$NEON_URL" \
CLERK_ISSUER='https://worthy-jackal-80.clerk.accounts.dev' \
CLERK_WEBHOOK_SECRET='whsec_dGVzdC1zZWNyZXQtdmFsdWUtMTIzNDU2Nzg5MA==' \
nohup ./venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 \
    > /tmp/orion_uvicorn_neon.log 2>&1 &

UVICORN_PID=$!
trap 'kill $UVICORN_PID 2>/dev/null' EXIT

# Esperar API
i=0
until curl -sf http://127.0.0.1:8000/ >/dev/null 2>&1; do
    i=$((i+1))
    if [ $i -gt 30 ]; then
        echo "TIMEOUT esperando API"; tail -30 /tmp/orion_uvicorn_neon.log; exit 1
    fi
    sleep 1
done
echo "API up tras ${i}s (apuntando a Neon)"

echo
echo "═══ Corriendo integration_test contra NEON develop ═══"
APP_ENV=prod \
DATABASE_URL="$NEON_URL" \
./venv/bin/python -m scripts.integration_test --label=neon "$@"


echo === Fase 5b: Daily Metrics ===
docker compose run --rm api python scripts/asset_metrics_test.py
if [ $? -ne 0 ]; then
  echo "  ❌ Fase 5b FALLÓ"
  exit 1
fi
echo "  ✅ Fase 5b: Daily Metrics OK"

