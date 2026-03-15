#!/bin/sh
set -e

provision_admin_user() {
python3 <<'PY'
import os

import bcrypt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from nativeauthenticator.orm import UserInfo

db_url = os.environ.get("JUPYTERHUB_DB_URL")
admin_user = os.environ.get("JUPYTERHUB_ADMIN_USER")
admin_password = os.environ.get("JUPYTERHUB_ADMIN_PASSWORD")

if not db_url or not admin_user or not admin_password:
    print("[JupyterHub] Admin bootstrap skipped: missing env vars.")
    raise SystemExit(0)

engine = create_engine(db_url)
UserInfo.__table__.create(engine, checkfirst=True)
Session = sessionmaker(bind=engine)
session = Session()

try:
    user = session.query(UserInfo).filter(UserInfo.username == admin_user).first()
    hashed_password = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt())

    if user is None:
        user = UserInfo(
            username=admin_user,
            password=hashed_password,
            is_authorized=True,
        )
        session.add(user)
        print(f"[JupyterHub] Created admin user '{admin_user}'.")
    else:
        user.password = hashed_password
        user.is_authorized = True
        print(f"[JupyterHub] Updated admin user '{admin_user}'.")

    session.commit()
finally:
    session.close()
PY
}

# Ensure DB schema exists (required for JupyterHub 4 + Postgres on first run)
echo "[JupyterHub] Running database upgrade..."
jupyterhub upgrade-db --config /srv/jupyterhub/jupyterhub_config.py 2>/dev/null || true
echo "[JupyterHub] Provisioning admin credentials from environment..."
provision_admin_user
exec "$@"
