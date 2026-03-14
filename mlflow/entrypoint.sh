#!/bin/sh
set -e

# ── Build PostgreSQL backend URI (URL-encode password for special chars) ───────
export MLFLOW_BACKEND_STORE_URI=$(python3 -c "
from urllib.parse import quote_plus
import os
p = os.environ.get('MLFLOW_DB_PASSWORD', '')
print(f\"postgresql://mlflow:{quote_plus(p)}@postgres-mlflow:5432/mlflow\")
")

# ── Write basic_auth.ini so the admin creds and auth DB come from env vars ─────
# Using the same PostgreSQL database as the tracking store is safe — auth
# migrations use a separate alembic version table (alembic_version_auth).
AUTH_DB_URI=$(python3 -c "
from urllib.parse import quote_plus
import os
p = os.environ.get('MLFLOW_DB_PASSWORD', '')
print(f\"postgresql://mlflow:{quote_plus(p)}@postgres-mlflow:5432/mlflow\")
")

mkdir -p /etc/mlflow
cat > /etc/mlflow/basic_auth.ini << EOF
[mlflow]
default_permission = READ
database_uri = ${AUTH_DB_URI}
admin_username = ${MLFLOW_ADMIN_USERNAME:-admin}
admin_password = ${MLFLOW_ADMIN_PASSWORD:-password1234}
EOF

export MLFLOW_AUTH_CONFIG_PATH=/etc/mlflow/basic_auth.ini

# ── Start MLflow with auth + multi-workspace support ──────────────────────────
# The server auto-initialises and migrates the DB on startup; running
# `mlflow db upgrade` standalone against an empty DB hits a broken migration
# dependency in 3.x (451aebb31d03_add_metric_step before metrics table exists).
exec mlflow server \
  --host 0.0.0.0 \
  --port 5000 \
  --default-artifact-root "${MLFLOW_DEFAULT_ARTIFACT_ROOT}" \
  --app-name basic-auth \
  --enable-workspaces \
  --workers 1
