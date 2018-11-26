FROM elyra/spark-py:v2.4.0

RUN apk add --no-cache build-base libffi-dev openssl-dev python-dev && \
    pip install cffi ipykernel ipython jupyter_client pycrypto

COPY kernel-launchers /usr/local/share/jupyter/kernel-launchers/

RUN adduser -S -u 1000 -G users jovyan && \
    chown -R jovyan:users /usr/local/share/jupyter /opt/spark/work-dir

USER jovyan


