FROM seldonio/mlserver:1.6.0

RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    mlserver-mlflow==1.6.0 \
    mlflow==3.10.1 \
    pyspark==3.5.1
