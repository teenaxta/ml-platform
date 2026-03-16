FROM apache/airflow:2.9.3

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

USER airflow
RUN pip install --no-cache-dir \
    dbt-trino==1.8.0 \
    mlflow==3.10.1 \
    numpy==1.26.4 \
    pandas==2.2.3 \
    psycopg2-binary \
    pyarrow \
    pyspark==3.5.1 \
    requests \
    trino

ENV JAVA_HOME=/usr/lib/jvm/default-java
