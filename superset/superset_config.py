from __future__ import annotations

import os

SQLALCHEMY_DATABASE_URI = (
    "postgresql+psycopg2://superset:"
    f"{os.environ.get('SUPERSET_DB_PASSWORD', 'SupersetDB444')}"
    "@postgres-superset:5432/superset"
)

SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY", "superset-demo-secret-key")
FEATURE_FLAGS = {
    "ENABLE_TEMPLATE_PROCESSING": True,
}
