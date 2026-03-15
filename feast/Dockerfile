FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl postgresql-client && rm -rf /var/lib/apt/lists/*

# All Feast deps baked in at build time — no pip install at runtime
RUN pip install --no-cache-dir \
    "feast[postgres,aws]==0.40.1" \
    psycopg2-binary \
    pgvector \
    pandas \
    pyarrow \
    s3fs

WORKDIR /opt/feast/project

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 6566 6567
ENTRYPOINT ["/entrypoint.sh"]
