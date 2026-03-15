# MLflow tracking server — PostgreSQL backend, S3/MinIO artifacts, basic-auth, workspaces
FROM ghcr.io/mlflow/mlflow:v3.10.1

# psycopg2-binary: PostgreSQL driver
# boto3: S3/MinIO artifact store
# mlflow[auth,genai]==3.10.1: basic-auth UI plus GenAI credential management
RUN pip install --no-cache-dir \
    psycopg2-binary \
    boto3 \
    'mlflow[auth,genai]==3.10.1'

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5000
ENTRYPOINT ["/entrypoint.sh"]
