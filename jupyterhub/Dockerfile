FROM quay.io/jupyterhub/jupyterhub:4.1.6

RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/default-java

RUN pip install --no-cache-dir \
    evidently==0.4.16 \
    "feast[aws]==0.40.1" \
    great_expectations==0.18.21 \
    jupyterhub-idle-culler==1.3.0 \
    jupyterhub-nativeauthenticator==1.2.0 \
    jupyterlab \
    joblib \
    matplotlib \
    mlflow==3.10.1 \
    notebook \
    numpy==1.26.4 \
    pandas==2.2.3 \
    psycopg2-binary \
    pyarrow \
    pyiceberg[s3,pandas] \
    pyspark==3.5.1 \
    scikit-learn==1.5.2 \
    seaborn \
    trino

WORKDIR /srv/jupyterhub
COPY entrypoint.sh /srv/jupyterhub/entrypoint.sh
RUN chmod +x /srv/jupyterhub/entrypoint.sh
ENTRYPOINT ["/srv/jupyterhub/entrypoint.sh"]
CMD ["jupyterhub", "--config", "/srv/jupyterhub/jupyterhub_config.py"]
