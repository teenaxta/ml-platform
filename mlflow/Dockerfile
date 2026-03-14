# MLflow tracking server with PostgreSQL backend support
FROM ghcr.io/mlflow/mlflow:v2.19.0

RUN pip install --no-cache-dir psycopg2-binary

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5000
ENTRYPOINT ["/entrypoint.sh"]
