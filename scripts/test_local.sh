#!/usr/bin/env bash
# Suite contra Docker local. Levanta el stack, corre tests, deja stack arriba.
set -e
cd "$(dirname "$0")/.."

echo "═══ Levantando stack Docker (down -v + up --build) ═══"
docker compose down -v >/dev/null 2>&1 || true
docker rm -f orion-postgres 2>/dev/null || true
CLERK_WEBHOOK_SECRET="whsec_dGVzdC1zZWNyZXQtdmFsdWUtMTIzNDU2Nzg5MA==" docker compose up -d --build

# Esperar API
i=0
until curl -sf http://127.0.0.1:8000/ >/dev/null 2>&1; do
    i=$((i+1))
    if [ $i -gt 90 ]; then
        echo "TIMEOUT esperando API"; docker compose logs api | tail -30; exit 1
    fi
    sleep 1
done
echo "API up tras ${i}s"

echo
echo "═══ Corriendo integration_test contra LOCAL ═══"
docker compose exec -T api python -m scripts.integration_test --label=local "$@"
