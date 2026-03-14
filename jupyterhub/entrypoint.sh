#!/bin/sh
set -e
# Ensure DB schema exists (required for JupyterHub 4 + Postgres on first run)
echo "[JupyterHub] Running database upgrade..."
jupyterhub upgrade-db --config /srv/jupyterhub/jupyterhub_config.py 2>/dev/null || true
exec "$@"
