FROM quay.io/jupyterhub/jupyterhub:4.1.6

RUN pip install --no-cache-dir \
    jupyterhub-nativeauthenticator==1.2.0 \
    jupyterhub-idle-culler==1.3.0 \
    notebook \
    jupyterlab \
    pyspark==3.5.1 \
    pyiceberg[s3,pandas] \
    scikit-learn \
    pandas \
    numpy \
    matplotlib \
    seaborn \
    joblib \
    psycopg2-binary \
    boto3 \
    feast[aws]==0.40.1

WORKDIR /srv/jupyterhub
COPY entrypoint.sh /srv/jupyterhub/entrypoint.sh
RUN chmod +x /srv/jupyterhub/entrypoint.sh
ENTRYPOINT ["/srv/jupyterhub/entrypoint.sh"]
CMD ["jupyterhub", "--config", "/srv/jupyterhub/jupyterhub_config.py"]
