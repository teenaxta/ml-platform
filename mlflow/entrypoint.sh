#!/bin/sh
set -e
# Build backend URI with URL-encoded password so special chars (@, :, etc.) don't break parsing
export MLFLOW_BACKEND_STORE_URI=$(python3 -c "
from urllib.parse import quote_plus
import os
p = os.environ.get('MLFLOW_DB_PASSWORD', '')
print(f\"postgresql://mlflow:{quote_plus(p)}@postgres-mlflow:5432/mlflow\")
")
exec mlflow server --host 0.0.0.0 --port 5000
