FROM seldonio/mlserver:1.6.0

USER root

RUN microdnf install -y --nodocs \
    java-17-openjdk-headless \
    && microdnf clean all

RUN pip install --no-cache-dir \
    mlserver-mlflow==1.6.0 \
    mlflow==3.10.1 \
    pyspark==3.5.1

USER 1000
