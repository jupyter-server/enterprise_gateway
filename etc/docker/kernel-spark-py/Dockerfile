FROM elyra/spark-py:v2.4.0

RUN apk add --no-cache build-base libffi-dev openssl-dev python-dev && \
    pip install cffi ipykernel ipython jupyter_client pycrypto

COPY kernel-launchers /usr/local/share/jupyter/kernel-launchers/

RUN addgroup -S -g 620 eg-kernel && adduser -S -u 620 -G eg-kernel eg-kernel && \
	chown -R eg-kernel.eg-kernel /usr/local/share/jupyter /opt/spark/work-dir

USER eg-kernel

