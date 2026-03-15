#!/bin/sh
set -e

export SUPERSET_CONFIG_PATH=/app/pythonpath/superset_config.py

superset db upgrade

superset fab create-admin \
  --username "${SUPERSET_ADMIN_USERNAME:-admin}" \
  --firstname "${SUPERSET_ADMIN_FIRSTNAME:-Admin}" \
  --lastname "${SUPERSET_ADMIN_LASTNAME:-User}" \
  --email "${SUPERSET_ADMIN_EMAIL:-admin@example.com}" \
  --password "${SUPERSET_ADMIN_PASSWORD:-SupersetAdmin888}" || true

if [ "${SUPERSET_ADMIN_USERNAME:-admin}" != "admin" ]; then
  superset fab create-admin \
    --username admin \
    --firstname Admin \
    --lastname User \
    --email admin@example.com \
    --password "${SUPERSET_ADMIN_PASSWORD:-SupersetAdmin888}" || true
fi

superset init

if [ "${SUPERSET_LOAD_EXAMPLES:-no}" = "yes" ]; then
  if [ ! -f /app/superset_home/.examples_loaded ]; then
    if superset load-examples; then
      touch /app/superset_home/.examples_loaded
    else
      echo "Skipping Superset bundled examples after load failure." >&2
    fi
  fi
fi

exec superset run -p 8088 --host 0.0.0.0
