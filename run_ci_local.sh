#!/usr/bin/env bash
set -e

CONTAINER_NAME="orion-test-pg"

cleanup() {
  echo
  echo "── Limpiando ──"
  [ -n "$UVICORN_PID" ] && kill -9 "$UVICORN_PID" 2>/dev/null || true
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  echo "Listo."
}
trap cleanup EXIT

echo "── 1/7 Levantando Postgres efímero ──"
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
docker run --name "$CONTAINER_NAME" \
  -e POSTGRES_USER=orion \
  -e POSTGRES_PASSWORD=orion \
  -e POSTGRES_DB=orion_test \
  -p 5432:5432 \
  -d postgres:16 >/dev/null

until docker exec "$CONTAINER_NAME" pg_isready -U orion >/dev/null 2>&1; do sleep 1; done
echo "Postgres listo."

export APP_ENV=dev
export DATABASE_URL_DEV="postgresql+asyncpg://orion:orion@localhost:5432/orion_test"
export DATABASE_TESTING="postgresql://orion:orion@localhost:5432/orion_test"
export CLERK_ISSUER="https://worthy-jackal-80.clerk.accounts.dev"
export ALLOWED_ORIGINS="http://localhost:3000"



echo "── 3/7 Migraciones ──"
alembic upgrade head

echo "── 4/7 Levantando uvicorn ──"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > /tmp/uvicorn.log 2>&1 &
UVICORN_PID=$!

echo "── 5/7 Esperando API ──"
for i in $(seq 1 60); do
  if curl -sf http://127.0.0.1:8000/ >/dev/null; then
    echo "API up tras ${i}s"
    break
  fi
  sleep 1
done

echo "── 6/7 Integration test ──"
python -m scripts.integration_test --label=ci

echo "── 7/7 OK ──"