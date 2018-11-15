FROM elyra/spark-py:v2.4.0

RUN apk add --no-cache build-base libffi-dev openssl-dev python-dev && \
    pip install cffi ipykernel ipython jupyter_client pycrypto

ADD jupyter_enterprise_gateway*.tar.gz /usr/local/share/jupyter/kernels/

RUN addgroup -S -g 620 eg-kernel && adduser -S -u 620 -G eg-kernel eg-kernel && \
	chown -R eg-kernel.eg-kernel /usr/local/share/jupyter /opt/spark/work-dir

USER eg-kernel

