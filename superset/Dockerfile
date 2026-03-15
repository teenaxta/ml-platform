FROM apache/superset:4.0.2

USER root
RUN pip install --no-cache-dir \
    psycopg2-binary \
    sqlalchemy-trino \
    trino

COPY superset_config.py /app/pythonpath/superset_config.py
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

USER superset
ENTRYPOINT ["/app/docker-entrypoint.sh"]
