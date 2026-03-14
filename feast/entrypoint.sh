#!/bin/sh
set -e
cd /opt/feast/project

echo "[Feast] Enabling pgvector extension..."
PGPASSWORD="${FEAST_DB_PASSWORD}" psql -h postgres-feast -U feast -d feast \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo "[Feast] Applying feature definitions..."
feast apply

echo "[Feast] Starting Web UI on :6567 ..."
feast ui --host 0.0.0.0 --port 6567 &

echo "[Feast] Starting feature server on :6566 ..."
exec feast serve --host 0.0.0.0 --port 6566
