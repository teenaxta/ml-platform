import os

# ── Authenticator  ───────────────────────────────────────────
c.JupyterHub.authenticator_class = "nativeauthenticator.NativeAuthenticator"

admin_user     = os.environ.get("JUPYTERHUB_ADMIN_USER", "admin")
admin_password = os.environ.get("JUPYTERHUB_ADMIN_PASSWORD", "changeme")

c.Authenticator.admin_users       = {admin_user}
c.NativeAuthenticator.open_signup = True          # users can self-register
c.NativeAuthenticator.check_common_password = True
c.NativeAuthenticator.minimum_password_length = 8

# JupyterHub 4.x: post_init_hooks removed (not supported). Create admin via UI signup
# or: docker compose exec jupyterhub jupyterhub add-user admin --password <pwd>

# ── Database  ────────────────────────────────────────────────
c.JupyterHub.db_url = os.environ.get(
    "JUPYTERHUB_DB_URL",
    "sqlite:////srv/jupyterhub/data/jupyterhub.sqlite"
)

# ── Spawner  ─────────────────────────────────────────────────
c.JupyterHub.spawner_class = "simple"
c.Spawner.default_url      = "/lab"
c.Spawner.args             = ["--allow-root"]
c.Spawner.mem_limit        = "4G"
c.Spawner.cpu_limit        = 2.0
c.Spawner.environment = {
    "SPARK_MASTER":          os.environ.get("SPARK_MASTER",          "spark://spark-master:7077"),
    "TRINO_HOST":            os.environ.get("TRINO_HOST",            "trino"),
    "TRINO_PORT":            os.environ.get("TRINO_PORT",            "8080"),
    "TRINO_USER":            os.environ.get("TRINO_USER",            "trino"),
    "TRINO_CATALOG":         os.environ.get("TRINO_CATALOG",         "iceberg"),
    "TRINO_SCHEMA":          os.environ.get("TRINO_SCHEMA",          "analytics"),
    "MLFLOW_TRACKING_URI":   os.environ.get("MLFLOW_TRACKING_URI",   "http://mlflow:5000"),
    "MLFLOW_TRACKING_USERNAME": os.environ.get("MLFLOW_TRACKING_USERNAME", ""),
    "MLFLOW_TRACKING_PASSWORD": os.environ.get("MLFLOW_TRACKING_PASSWORD", ""),
    "ICEBERG_JDBC_URI":      os.environ.get("ICEBERG_JDBC_URI",      "jdbc:postgresql://postgres-iceberg:5432/iceberg_catalog"),
    "ICEBERG_JDBC_USER":     os.environ.get("ICEBERG_JDBC_USER",     "iceberg"),
    "ICEBERG_JDBC_PASSWORD": os.environ.get("ICEBERG_JDBC_PASSWORD", "iceberg123"),
    "DEMO_POSTGRES_HOST":    os.environ.get("DEMO_POSTGRES_HOST",    "demo-postgres"),
    "DEMO_POSTGRES_PORT":    os.environ.get("DEMO_POSTGRES_PORT",    "5432"),
    "DEMO_POSTGRES_DB":      os.environ.get("DEMO_POSTGRES_DB",      "retail_db"),
    "DEMO_POSTGRES_USER":    os.environ.get("DEMO_POSTGRES_USER",    "analyst"),
    "DEMO_POSTGRES_PASSWORD": os.environ.get("DEMO_POSTGRES_PASSWORD", "analyst123"),
    "AWS_ACCESS_KEY_ID":     os.environ.get("AWS_ACCESS_KEY_ID",     ""),
    "AWS_SECRET_ACCESS_KEY": os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
    "AWS_REGION":            os.environ.get("AWS_REGION",            "us-east-1"),
    "AWS_DEFAULT_REGION":    os.environ.get("AWS_DEFAULT_REGION",    "us-east-1"),
    "AWS_S3_ENDPOINT":       os.environ.get("AWS_S3_ENDPOINT",       "http://minio:9000"),
    "JAVA_HOME":             os.environ.get("JAVA_HOME",             "/usr/lib/jvm/default-java"),
    "PYSPARK_PYTHON":        "python3",
    "PYSPARK_DRIVER_PYTHON": "python3",
}

# ── Hub networking  ──────────────────────────────────────────
c.JupyterHub.hub_ip = "0.0.0.0"
c.JupyterHub.ip     = "0.0.0.0"
c.JupyterHub.port   = 8000

# ── Idle culler (stop servers after 1 h idle)  ───────────────
c.JupyterHub.services = [{
    "name": "idle-culler",
    "command": [
        "python3", "-m", "jupyterhub_idle_culler",
        "--timeout=3600",
        "--max-age=86400",
    ],
}]

# ── RBAC roles  ──────────────────────────────────────────────
c.JupyterHub.load_roles = [
    {
        "name": "admin",
        "users": [admin_user],
    },
    {
        "name": "user",
        "description": "Own server only",
        "scopes": ["self"],
    },
    {
        "name": "idle-culler",
        "scopes": [
            "list:users",
            "read:users:activity",
            "read:servers",
            "admin:servers",
        ],
        "services": ["idle-culler"],
    },
]

# ── Security  ────────────────────────────────────────────────
c.JupyterHub.cookie_secret_file  = "/srv/jupyterhub/data/jupyterhub_cookie_secret"
c.JupyterHub.cookie_max_age_days = 0.33   # 8-hour sessions
c.JupyterHub.log_level           = "INFO"
