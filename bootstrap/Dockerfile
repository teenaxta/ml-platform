FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    mlflow==3.10.1 \
    numpy==1.26.4 \
    pandas==2.2.3 \
    psycopg2-binary \
    pyarrow \
    pyspark==3.5.1 \
    scikit-learn==1.5.2 \
    trino

ENV JAVA_HOME=/usr/lib/jvm/default-java
